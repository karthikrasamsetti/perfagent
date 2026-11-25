"""Launch a pinned managed worker without networking or application credentials."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from perfagent.data.filenames import safe_runner_data_filename

_IMAGE = re.compile(r"(?:[a-z0-9][a-z0-9./:_-]*@)?sha256:[a-f0-9]{64}")
_MAX_INPUT_SIZE = 5 * 1024 * 1024


class WorkerUnavailable(RuntimeError):
    """A managed worker could not be launched or cleaned up."""


@contextmanager
def docker_worker(
    image: str,
    bridge: Path,
    content: str,
    *,
    max_seconds: int,
    max_clients: int,
    data_filename: str = "",
    data_content: str = "",
):
    """Yield the attached Docker process for streaming metrics. Always remove the container."""
    if not _IMAGE.fullmatch(image):
        raise ValueError("A digest-pinned worker image is required.")
    if not 1 <= max_seconds <= 3600 or not 1 <= max_clients <= 1000:
        raise ValueError("Worker limits are out of range.")
    if len(content.encode()) + len(data_content.encode()) > _MAX_INPUT_SIZE:
        raise ValueError("The worker inputs exceed 5 MiB.")
    bridge = bridge.resolve(strict=True)
    identity = bridge.stat()
    if not stat.S_ISSOCK(identity.st_mode) or stat.S_IMODE(identity.st_mode) != 0o600:
        raise ValueError("A private worker socket is required.")
    if not hasattr(os, "getuid") or os.getuid() == 0 or identity.st_uid != os.getuid():
        raise WorkerUnavailable("Run the managed worker supervisor as the socket's non-root owner.")

    name = "perfagent-worker-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="pa-job-") as directory:
        inputs = Path(directory) / "inputs"
        inputs.mkdir(mode=0o755)
        script = inputs / "loadtest.js"
        script.write_text(content, encoding="utf-8")
        script.chmod(0o444)
        if data_filename and data_content:
            dataset = inputs / safe_runner_data_filename(data_filename)
            if dataset == script:
                raise ValueError("The dataset filename conflicts with the saved script.")
            dataset.write_text(data_content, encoding="utf-8")
            dataset.chmod(0o444)
        if any("," in str(path) for path in (inputs, bridge)):
            raise ValueError("Worker mount paths cannot contain commas.")
        command = [
            "docker",
            "create",
            "--name",
            name,
            "--pull=never",
            "--network=none",
            "--init",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--user={os.getuid()}:{os.getgid()}",
            "--pids-limit=128",
            "--memory=256m",
            "--cpus=1",
            "--log-driver=none",
            "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=32m",
            "--mount",
            f"type=bind,src={inputs},dst=/job,readonly",
            "--mount",
            f"type=bind,src={bridge},dst=/egress.sock,readonly",
        ]
        command.extend(
            f"--env={key}="
            for key in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "NO_PROXY",
                "ALL_PROXY",
                "FTP_PROXY",
                "http_proxy",
                "https_proxy",
                "no_proxy",
                "all_proxy",
                "ftp_proxy",
            )
        )
        command.extend(
            [
                image,
                "--script",
                "/job/loadtest.js",
                "--bridge",
                "/egress.sock",
                "--max-seconds",
                str(max_seconds),
                "--max-clients",
                str(max_clients),
            ]
        )
        process = None
        created = False
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode:
                raise WorkerUnavailable("Docker could not create the managed worker.")
            created = True
            process = subprocess.Popen(
                ["docker", "start", "--attach", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            yield process
        finally:
            try:
                result = subprocess.run(
                    ["docker", "rm", "-f", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
                if created and result.returncode:
                    raise WorkerUnavailable("Docker could not remove the managed worker.")
            finally:
                if process is not None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    for stream in (process.stdout, process.stderr):
                        if stream:
                            stream.close()
