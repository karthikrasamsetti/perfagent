"""Inspect saved scripts in resource-bounded Docker containers with no network."""

import re
import subprocess
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

from perfagent.data.filenames import safe_runner_data_filename

_IMAGE = re.compile(r"[a-z0-9][a-z0-9./:_-]*@sha256:[a-f0-9]{64}")
_SLOT = threading.BoundedSemaphore(1)


def validate_isolated(image: str, content: str, filename: str, data: str) -> dict:
    if not _IMAGE.fullmatch(image):
        return {
            "ok": False,
            "status": "unavailable",
            "message": "A digest-pinned k6 image is required.",
        }
    if len(content.encode()) + len(data.encode()) > 5 * 1024 * 1024:
        return {"ok": False, "status": "invalid", "message": "Isolated inputs exceed 5 MiB."}
    if not _SLOT.acquire(blocking=False):
        return {"ok": False, "status": "busy", "message": "The isolated validator is busy."}
    name = "perfagent-inspect-" + uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix="perfagent-inspect-") as directory:
            inputs = Path(directory) / "inputs"
            if ":" in directory:
                raise ValueError("Invalid Docker mount path")
            inputs.mkdir(mode=0o755)
            (inputs / "loadtest.js").write_text(content, encoding="utf-8")
            (inputs / "loadtest.js").chmod(0o444)
            if filename and data:
                path = inputs / safe_runner_data_filename(filename)
                if path.name == "loadtest.js":
                    raise ValueError("Dataset conflicts with script name")
                path.write_text(data, encoding="utf-8")
                path.chmod(0o444)
            command = [
                "docker",
                "create",
                "--name",
                name,
                "--pull=never",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--user=65534:65534",
                "--pids-limit=64",
                "--memory=128m",
                "--cpus=0.5",
                "--log-driver=none",
                "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m",
                "--env=HOME=/tmp",
                "--workdir=/input",
                "-v",
                f"{inputs}:/input:ro",
            ]
            # Docker client proxy configuration can otherwise be injected into containers.
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
            created = subprocess.run(
                [*command, image, "inspect", "/input/loadtest.js"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            if created.returncode != 0:
                return {
                    "ok": False,
                    "status": "unavailable",
                    "message": "Docker could not create the pinned container.",
                }
            result = subprocess.run(
                ["docker", "start", "--attach", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                return {"ok": True, "status": "ok", "message": "Passed isolated k6 inspection."}
            if result.returncode == 125:
                return {
                    "ok": False,
                    "status": "unavailable",
                    "message": "Docker could not start the pinned image.",
                }
            return {
                "ok": False,
                "status": "invalid",
                "message": "The script did not pass isolated k6 inspection.",
            }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "timeout",
            "message": "Isolated k6 inspection exceeded its deadline.",
        }
    except (OSError, ValueError):
        return {
            "ok": False,
            "status": "unavailable",
            "message": "Could not prepare isolated k6 inspection.",
        }
    finally:
        try:
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        _SLOT.release()
