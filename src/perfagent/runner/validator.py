"""Validate a generated k6 script before a full run.

Uses `k6 inspect`, which parses the script and its options/scenarios and reports any
problems WITHOUT running load. This catches syntax errors, bad imports, and invalid
configuration in a fraction of a second.

Why not `k6 run --vus 1 --iterations 1`? Those CLI flags override a script's
`scenarios` block entirely, which makes k6 look for a `export default` function. Our
scripts use named `scenarios` + `exec` functions (no default export), so that
approach falsely reports "function 'default' not found". `k6 inspect` has no such
problem — it validates the script as written.

Deterministic, no LLM. Needs k6 on PATH (same as a real run).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def k6_available() -> bool:
    return shutil.which("k6") is not None


def validate_script(content: str, data_filename: str = "", data_content: str = "",
                    timeout: float = 20.0) -> dict:
    """Validate a k6 script with `k6 inspect`. Returns a result dict.

    {
      "ok": bool,
      "status": "valid" | "failed" | "k6_missing" | "timeout" | "error",
      "message": str,
      "detail": str,
    }
    """
    if not k6_available():
        return {
            "ok": False, "status": "k6_missing",
            "message": "k6 is not installed or not on PATH — cannot validate.",
            "detail": "",
        }

    tmpdir = tempfile.mkdtemp(prefix="perfagent_validate_")
    try:
        script_path = Path(tmpdir) / "loadtest.js"
        script_path.write_text(content, encoding="utf-8")
        if data_filename and data_content:
            (Path(tmpdir) / data_filename).write_text(data_content, encoding="utf-8")

        # `k6 inspect` parses the script + options and exits non-zero on problems.
        cmd = ["k6", "inspect", str(script_path)]
        try:
            proc = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False, "status": "timeout",
                "message": f"Validation timed out after {int(timeout)}s.",
                "detail": "",
            }

        if proc.returncode == 0:
            # inspect prints the parsed config as JSON on success; confirm it parsed.
            scenarios = _scenario_count(proc.stdout)
            extra = f" ({scenarios} scenario(s) detected)" if scenarios else ""
            return {
                "ok": True, "status": "valid",
                "message": f"Script is valid — it parsed and its configuration is sound{extra}.",
                "detail": "",
            }

        err = (proc.stderr or proc.stdout or "").strip()
        return {
            "ok": False, "status": "failed",
            "message": "Script failed validation — fix this before running.",
            "detail": _tail(err) or f"k6 inspect exited {proc.returncode}",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False, "status": "error",
            "message": f"Could not validate the script: {e}",
            "detail": "",
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _scenario_count(stdout: str) -> int:
    try:
        data = json.loads(stdout)
        scen = data.get("scenarios", {})
        return len(scen) if isinstance(scen, dict) else 0
    except (json.JSONDecodeError, AttributeError):
        return 0


def _tail(text: str, max_chars: int = 600) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return "…" + text[-max_chars:]