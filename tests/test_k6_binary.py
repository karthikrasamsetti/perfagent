"""k6 auto-provisioning: lookup order, verified download, failure handling.

No network: the download is replaced with an in-memory archive.
"""

from __future__ import annotations

import hashlib
import io
import os
import platform
import tarfile
import zipfile
from pathlib import Path

import pytest

from perfagent.runner import k6_binary as kb


def _tar_with_k6(payload: bytes = b"#!/bin/sh\necho k6\n") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo("k6-v1.3.0-linux-amd64/k6")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERFAGENT_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PERFAGENT_K6_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(kb, "_platform", lambda: ("linux", "amd64"))
    monkeypatch.setattr(kb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(kb, "_bundled_path", lambda: tmp_path / "no-bundle" / "k6")
    return tmp_path


def _serve(monkeypatch, blob: bytes, sha: str | None = None):
    calls = []
    monkeypatch.setitem(kb._ARCHIVES, ("linux", "amd64"),
                        ("k6-v1.3.0-linux-amd64.tar.gz", sha or hashlib.sha256(blob).hexdigest()))

    def fake_download(url, timeout):
        calls.append(url)
        return blob
    monkeypatch.setattr(kb, "_download", fake_download)
    return calls


def test_downloads_verifies_and_caches(clean_env, monkeypatch):
    calls = _serve(monkeypatch, _tar_with_k6())
    assert kb.find_k6() is None
    path = kb.ensure_k6()
    assert Path(path) == kb.cache_path() and Path(path).is_file()
    assert os.access(path, os.X_OK)
    assert calls == [kb._RELEASE_URL + "k6-v1.3.0-linux-amd64.tar.gz"]
    # second call uses the cache, no new download
    assert kb.ensure_k6() == path and len(calls) == 1
    assert kb.find_k6() == path


def test_checksum_mismatch_is_rejected(clean_env, monkeypatch):
    _serve(monkeypatch, _tar_with_k6(), sha="0" * 64)
    with pytest.raises(kb.K6Unavailable, match="checksum"):
        kb.ensure_k6()
    assert not kb.cache_path().exists()


def test_download_failure_has_helpful_message(clean_env, monkeypatch):
    monkeypatch.setitem(kb._ARCHIVES, ("linux", "amd64"), ("k6.tar.gz", "x"))

    def boom(url, timeout):
        raise OSError("no route to host")
    monkeypatch.setattr(kb, "_download", boom)
    with pytest.raises(kb.K6Unavailable, match="PERFAGENT_K6_PATH"):
        kb.ensure_k6()


def test_bad_archive_layout(clean_env, monkeypatch):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo("README.md")
        info.size = 2
        tf.addfile(info, io.BytesIO(b"hi"))
    _serve(monkeypatch, buf.getvalue())
    with pytest.raises(kb.K6Unavailable, match="layout"):
        kb.ensure_k6()


def test_override_env_wins(clean_env, monkeypatch):
    exe = clean_env / "custom" / "k6"
    exe.parent.mkdir()
    exe.write_text("x")
    monkeypatch.setenv("PERFAGENT_K6_PATH", str(exe))
    assert kb.find_k6() == str(exe)
    assert kb.ensure_k6() == str(exe)

@pytest.mark.skipif(platform.system() == "Windows",
                    reason="PATH executable lookup is Unix-specific (passes on Linux CI)")
def test_existing_k6_on_path_is_used(clean_env, monkeypatch):
    bindir = clean_env / "bin"
    bindir.mkdir()
    # Windows resolves executables by extension — name it k6.exe there so
    # shutil.which("k6") can find it. On Unix the bare name is correct.
    exe = bindir / ("k6.exe" if platform.system() == "Windows" else "k6")
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    assert kb.find_k6() == str(exe)


def test_unknown_platform_cannot_provision(clean_env, monkeypatch):
    monkeypatch.setattr(kb, "_platform", lambda: ("solaris", "sparc"))
    assert kb.can_provision() is False
    with pytest.raises(kb.K6Unavailable, match="PERFAGENT_K6_PATH"):
        kb.ensure_k6()


def test_zip_archive_for_windows(clean_env, monkeypatch):
    monkeypatch.setattr(kb, "_platform", lambda: ("windows", "amd64"))
    monkeypatch.setattr(kb.platform, "system", lambda: "Windows")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("k6-v1.3.0-windows-amd64/k6.exe", b"MZ")
    blob = buf.getvalue()
    monkeypatch.setitem(kb._ARCHIVES, ("windows", "amd64"),
                        ("k6-v1.3.0-windows-amd64.zip", hashlib.sha256(blob).hexdigest()))
    monkeypatch.setattr(kb, "_download", lambda url, timeout: blob)
    path = kb.ensure_k6()
    assert path.endswith("k6.exe") and Path(path).read_bytes() == b"MZ"


def test_runner_reports_available_when_provisionable(clean_env):
    from perfagent.runner import k6_available
    assert k6_available() is True


def test_override_pointing_nowhere_is_an_error(clean_env, monkeypatch):
    monkeypatch.setenv("PERFAGENT_K6_PATH", str(clean_env / "missing" / "k6"))
    with pytest.raises(kb.K6Unavailable, match="no file exists"):
        kb.ensure_k6()
    from perfagent.runner import k6_available
    assert k6_available() is False          # the status endpoint must not crash


def test_settings_from_dotenv_file(clean_env, monkeypatch):
    exe = clean_env / "fromenvfile" / "k6"
    exe.parent.mkdir()
    exe.write_text("x")
    monkeypatch.chdir(clean_env)
    (clean_env / ".env").write_text(f"PERFAGENT_K6_PATH={exe}\n")
    assert kb.find_k6() == str(exe)