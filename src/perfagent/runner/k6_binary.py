"""Locate or auto-provision the k6 binary so customers never install it by hand.

Resolution order (first hit wins):
  1. PERFAGENT_K6_PATH env var          -> explicit override (air-gapped installs)
  2. Bundled binary inside the package  -> perfagent/runner/bin/<os>-<arch>/k6[.exe]
  3. Managed cache                      -> ~/.perfagent/bin/k6-<ver>/k6[.exe]
  4. k6 already on PATH                 -> use what the customer has
  5. Download the pinned release from GitHub, verify SHA-256, cache it (step 3)

The download is pinned to one version and checked against hashes hard-coded here,
so a tampered or swapped archive is rejected rather than executed. It uses only the
Python standard library (urllib), which also honours HTTPS_PROXY / HTTP_PROXY.

PERFAGENT_K6_PATH and PERFAGENT_HOME can be set in .env or as environment variables.
"""

from __future__ import annotations

import hashlib
import io
import os
import platform
import shutil
import stat
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from perfagent.config import Settings

K6_VERSION = "v1.3.0"

# SHA-256 of the official release archives (from k6-v1.3.0-checksums.txt).
_ARCHIVES: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "amd64"):   ("k6-v1.3.0-linux-amd64.tar.gz",
                           "84d26fc1f7bc03e02f2e016b3b1b20c032e05dfe461fca82de4e3a6ebe72ddbd"),
    ("linux", "arm64"):   ("k6-v1.3.0-linux-arm64.tar.gz",
                           "df35a88b5ef534b39f4ab74b22a0d60362138af219228253f042650a36af7920"),
    ("macos", "amd64"):   ("k6-v1.3.0-macos-amd64.zip",
                           "43d1ba79139856a3be056bf19b748ae68096fd67575df5afdc27514ec7adb8dc"),
    ("macos", "arm64"):   ("k6-v1.3.0-macos-arm64.zip",
                           "eb06b22418e26f7394023e53aaaddf0bec739f669acf718cc9b0e2d7f12bd7be"),
    ("windows", "amd64"): ("k6-v1.3.0-windows-amd64.zip",
                           "06a15d69869efb9261e6c132af64078731ad7d048095eaca05198daacb17686d"),
}

_RELEASE_URL = f"https://github.com/grafana/k6/releases/download/{K6_VERSION}/"
_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
_lock = threading.Lock()


class K6Unavailable(RuntimeError):
    """Raised when k6 can't be found and can't be downloaded."""


def _settings() -> Settings:
    # Read fresh (not the cached get_settings()) so a changed .env / env var is
    # picked up without restarting; this is only called when a run or validation starts.
    return Settings()


def _platform() -> tuple[str, str]:
    sysname = platform.system().lower()
    os_name = {"linux": "linux", "darwin": "macos", "windows": "windows"}.get(sysname, sysname)
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    return os_name, arch


def _exe_name() -> str:
    return "k6.exe" if platform.system() == "Windows" else "k6"


def _bundled_path() -> Path:
    os_name, arch = _platform()
    return Path(__file__).parent / "bin" / f"{os_name}-{arch}" / _exe_name()


def cache_path() -> Path:
    """Where a downloaded k6 is kept: <PERFAGENT_HOME or ~/.perfagent>/bin/k6-<ver>/."""
    home = _settings().perfagent_home.strip()
    root = Path(home) if home else Path.home() / ".perfagent"
    return root / "bin" / f"k6-{K6_VERSION}" / _exe_name()


def find_k6() -> str | None:
    """Return a usable k6 path without downloading anything, or None."""
    override = _settings().perfagent_k6_path.strip()
    if override:
        if Path(override).is_file():
            return override
        raise K6Unavailable(f"PERFAGENT_K6_PATH is set to {override!r}, but no file exists there")
    for p in (_bundled_path(), cache_path()):
        if p.is_file():
            return str(p)
    return shutil.which("k6")


def k6_ready_or_provisionable() -> bool:
    """True if k6 is present, or can be fetched automatically. Never raises."""
    try:
        return find_k6() is not None or can_provision()
    except K6Unavailable:
        return False


def can_provision() -> bool:
    """True if a pinned k6 build exists for this OS/CPU, so it can be downloaded."""
    return _platform() in _ARCHIVES


def _download(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        data = resp.read(_MAX_DOWNLOAD_BYTES + 1)
    if len(data) > _MAX_DOWNLOAD_BYTES:
        raise K6Unavailable("k6 download is unexpectedly large; refusing it")
    return data


def ensure_k6(timeout: float = 120.0) -> str:
    """Return a k6 path, downloading and verifying the pinned release if needed."""
    found = find_k6()
    if found:
        return found
    if not can_provision():
        raise K6Unavailable(
            f"no prebuilt k6 for this platform {_platform()}; set PERFAGENT_K6_PATH to a k6 binary"
        )

    with _lock:  # two runs starting at once shouldn't download twice
        found = find_k6()
        if found:
            return found

        archive, expected_sha = _ARCHIVES[_platform()]
        try:
            blob = _download(_RELEASE_URL + archive, timeout)
        except K6Unavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise K6Unavailable(
                f"could not download k6 ({type(e).__name__}). If this machine has no internet "
                "access, set PERFAGENT_K6_PATH to a k6 binary or ship the bundled binary."
            ) from e

        if hashlib.sha256(blob).hexdigest() != expected_sha:
            raise K6Unavailable(f"k6 checksum mismatch for {archive}; refusing to run it")

        exe = _exe_name()
        try:
            if archive.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    member = next(n for n in zf.namelist() if n.endswith("/" + exe))
                    data = zf.read(member)
            else:
                with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
                    member = next(m for m in tf.getmembers() if m.name.endswith("/" + exe))
                    data = tf.extractfile(member).read()  # type: ignore[union-attr]
        except (StopIteration, zipfile.BadZipFile, tarfile.TarError) as e:
            raise K6Unavailable(f"k6 archive {archive} has an unexpected layout") from e

        dest = cache_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, dest)  # atomic: a half-written binary is never picked up
        return str(dest)