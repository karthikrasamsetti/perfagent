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

from perfagent.data.filenames import safe_runner_data_filename
from perfagent.runner.k6_binary import K6Unavailable, ensure_k6, k6_ready_or_provisionable
from perfagent.runner.process_environment import k6_process_environment


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
            (Path(tmpdir) / safe_runner_data_filename(data_filename)).write_text(data_content, encoding="utf-8")

        # `k6 inspect` parses the script + options and exits non-zero on problems.
        cmd = [k6_path, "inspect", str(script_path)]
        try:
            proc = subprocess.run(
                cmd, cwd=tmpdir, env=k6_process_environment(tmpdir),
                capture_output=True, text=True, timeout=timeout,
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

_VERIFICATION_WRAPPER = """
import { check, group } from 'k6';
import * as source from './loadtest.js';

const { scenarios, stages, duration, iterations, vus, thresholds, ...settings } = source.options || {};
const journeys = Object.entries(scenarios || { default: { exec: 'default' } });
if (journeys.length < 1 || journeys.length > 20) {
  throw new Error('Verification supports 1 to 20 journeys.');
}
if (journeys.some(([, scenario]) => Object.keys(scenario.env || {}).length)) {
  throw new Error('Verification cannot replay scenario-specific environment overrides.');
}
export const options = {
  ...settings, scenarios: {}, maxRedirects: 0,
  systemTags: ['group', 'status', 'method', 'name', 'check'],
};
export function setup() { return source.setup?.(); }
export function teardown(data) { source.teardown?.(data); }
export default function (data) {
  for (const [name, scenario] of journeys) {
    group('verify__' + name, () => {
      let completed = false;
      try {
        source[scenario.exec || 'default'](data);
        completed = true;
      } catch (_) {
        // Report this journey as incomplete and continue with the remaining ones.
      }
      check(completed, { 'Journey completed': result => result });
    });
  }
}
"""


def _verification_results(metrics_path: Path) -> list[dict]:
    """Read status and check results without retaining response bodies or request URLs."""
    journeys: dict[str, dict] = {}
    if not metrics_path.exists():
        return []
    with metrics_path.open(encoding="utf-8") as metrics:
        for line in metrics:
            sample = json.loads(line)
            metric = sample.get("metric")
            if sample.get("type") != "Point" or metric not in {"http_reqs", "checks"}:
                continue
            data = sample["data"]
            tags = data.get("tags", {})
            group_name = tags.get("group", "").split("::")[1:2]
            if not group_name or not group_name[0].startswith("verify__"):
                continue
            name = group_name[0].removeprefix("verify__")
            journey = journeys.setdefault(name, {
                "name": name, "requests": [], "checks": [], "completed": False,
            })
            if metric == "http_reqs":
                status = int(tags.get("status", "0"))
                journey["requests"].append({
                    "method": tags.get("method"), "status": status, "ok": 200 <= status < 400,
                })
            else:
                check = tags.get("check", "Response check")
                if check == "Journey completed" and tags["group"] == "::" + group_name[0]:
                    journey["completed"] = bool(data["value"])
                else:
                    journey["checks"].append({"name": check, "ok": bool(data["value"])})
    for journey in journeys.values():
        journey["ok"] = (journey["completed"] and bool(journey["requests"])
                         and all(item["ok"] for item in journey["requests"] + journey["checks"]))
    return list(journeys.values())


def preflight_script(content: str, data_filename: str = "", data_content: str = "",
                     timeout: float = 30.0) -> dict:
    """Exercise each configured journey once using one VU and a bounded runtime."""
    result = {"mode": "script", "all_ok": False, "journeys": []}
    try:
        k6 = _k6_path()
        with tempfile.TemporaryDirectory(prefix="perfagent_preflight_") as tmpdir:
            directory = Path(tmpdir)
            (directory / "loadtest.js").write_text(content, encoding="utf-8")
            if data_filename and data_content:
                (directory / safe_runner_data_filename(data_filename)).write_text(data_content, encoding="utf-8")
            entry = directory / "perfagent-preflight.js"
            entry.write_text(_VERIFICATION_WRAPPER, encoding="utf-8")
            metrics = directory / "perfagent-verification.jsonl"
            proc = subprocess.run(
                [k6, "run", "--address=", "--quiet", "--vus", "1", "--iterations", "1",
                 "--rps", "10", "-e", "PERFAGENT_VERIFY=1", "--out", f"json={metrics}", str(entry)],
                cwd=tmpdir, env=k6_process_environment(tmpdir),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
            )
            journeys = _verification_results(metrics)
    except subprocess.TimeoutExpired:
        return {**result, "message": f"Verification timed out after {int(timeout)} seconds."}
    except (K6Unavailable, OSError, ValueError):
        return {**result, "message": "Verification could not run. Check that k6 and the test inputs are available."}

    all_ok = bool(journeys) and not proc.returncode and all(journey["ok"] for journey in journeys)
    if all_ok:
        message = f"Verification passed for {len(journeys)} {'journey' if len(journeys) == 1 else 'journeys'}."
    elif journeys:
        message = "Verification failed. Review the request and response check results."
    else:
        message = ("Verification did not complete a journey. Validate the script and check "
                   "that it uses supported HTTP journeys without scenario-specific environment overrides.")
    return {**result, "all_ok": all_ok, "journeys": journeys, "message": message}
