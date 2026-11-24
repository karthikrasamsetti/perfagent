"""Validate a generated k6 script before a full run.

Uses `k6 inspect`, which parses the script and its options/scenarios and reports any
problems WITHOUT running load. This catches syntax errors, bad imports, and invalid
configuration in a fraction of a second.

Edited script pre-flight uses a wrapper with a default export so k6's one-iteration
CLI options can call a script whose scenario uses a named export.

Deterministic, no LLM. k6 is located or auto-provisioned by k6_binary (same as a
real run), so the customer doesn't install it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from perfagent.runner.k6_binary import K6Unavailable, ensure_k6, k6_ready_or_provisionable


def k6_available() -> bool:
    """True if k6 is present, or can be fetched automatically on first use."""
    return k6_ready_or_provisionable()


def _k6_path() -> str:
    """Path to k6, downloading the pinned release on first use (raises K6Unavailable)."""
    return ensure_k6()


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
            "message": "The k6 load engine is not available on this platform — cannot validate. "
                       "Set PERFAGENT_K6_PATH to a k6 binary.",
            "detail": "",
        }
    try:
        k6_path = _k6_path()
    except K6Unavailable as e:
        return {"ok": False, "status": "k6_missing", "message": f"Cannot validate: {e}", "detail": ""}

    tmpdir = tempfile.mkdtemp(prefix="perfagent_validate_")
    try:
        script_path = Path(tmpdir) / "loadtest.js"
        script_path.write_text(content, encoding="utf-8")
        if data_filename and data_content:
            (Path(tmpdir) / data_filename).write_text(data_content, encoding="utf-8")

        # `k6 inspect` parses the script + options and exits non-zero on problems.
        cmd = [k6_path, "inspect", str(script_path)]
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

def preflight_script(content: str, data_filename: str = "", data_content: str = "",
                     timeout: float = 30.0) -> dict:
    """Run one iteration of the first configured scenario of an edited script."""
    wrapper = """
import * as source from './loadtest.js';
const { scenarios, stages, duration, iterations, vus, thresholds, ...settings } = source.options || {};
const scenario = Object.values(scenarios || {})[0];
const execute = source[scenario?.exec || 'default'];
export const options = { ...settings, thresholds: {
  http_req_failed: ['rate==0'], checks: ['rate==1'], iterations: ['count==1'],
} };
export function setup() { return source.setup?.(); }
export function teardown(data) { source.teardown?.(data); }
export default function (data) { return execute(data); }
"""
    result = {"mode": "script", "all_ok": False}
    try:
        k6 = _k6_path()
        with tempfile.TemporaryDirectory(prefix="perfagent_preflight_") as tmpdir:
            directory = Path(tmpdir)
            source = directory / "loadtest.js"
            source.write_text(content, encoding="utf-8")
            if data_filename and data_content:
                (directory / data_filename).write_text(data_content, encoding="utf-8")
            entry = directory / "perfagent-preflight.js"
            entry.write_text(wrapper, encoding="utf-8")
            proc = subprocess.run(
                [k6, "run", "--address=", "--quiet", "--vus", "1", "--iterations", "1", str(entry)],
                cwd=tmpdir, capture_output=True, text=True, timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return {**result, "message": f"Script pre-flight timed out after {int(timeout)} seconds."}
    except (K6Unavailable, OSError) as exc:
        return {**result, "message": f"Could not run script pre-flight: {exc}"}
    if proc.returncode or 'level=error' in proc.stderr:
        return {**result, "message": "Script pre-flight failed. " + _tail(proc.stderr or proc.stdout)}
    return {**result, "all_ok": True,
            "message": "Script pre-flight passed. One iteration of the first configured scenario completed."}
