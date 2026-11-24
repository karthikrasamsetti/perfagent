"""Keep service credentials and configuration out of local k6 subprocesses."""

import os
from pathlib import Path

_SYSTEM_KEYS = {"LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT", "WINDIR",
                "SSL_CERT_FILE", "SSL_CERT_DIR"}


def k6_process_environment(directory: str | Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key.upper() in _SYSTEM_KEYS}
    # Use the existing per-run directory for k6's home, config and temporary files.
    workspace = str(directory)
    env.update(dict.fromkeys(
        ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "APPDATA", "LOCALAPPDATA", "TMPDIR", "TMP", "TEMP"),
        workspace,
    ))
    return env
