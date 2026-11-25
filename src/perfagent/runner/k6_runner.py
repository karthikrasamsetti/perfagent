"""The Runner: execute a k6 script as a subprocess and stream live metrics.

Design (matches the trust boundary):
  - k6 does the load and emits raw per-request metrics as JSON lines.
  - This module PARSES and AGGREGATES those deterministically in Python — every
    number the UI shows (RPS, error rate, p95) is computed here, in code, not by
    an LLM.
  - Runs are tracked in memory by run_id; the API polls get_run() for live status.
  - If the script is data-parameterized, the uploaded data file is written next to
    the script so k6's open('./file') finds it.
  - k6's human-readable output (console.log/error from the script, threshold
    crossings, the checks summary) goes to STDERR; we capture those lines into
    run.logs for the "Live run logs" panel.

k6 does NOT need to be installed by the customer: k6_binary.ensure_k6() finds a
bundled/cached copy or downloads the pinned, checksum-verified release on first run.
If that fails (e.g. offline), the run is marked 'error' with a clear message.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from perfagent.config import get_settings
from perfagent.data.filenames import safe_runner_data_filename
from perfagent.guardrails.redaction import redact_text, restore
from perfagent.runner.k6_binary import K6Unavailable, ensure_k6, find_k6, k6_ready_or_provisionable
from perfagent.runner.process_environment import k6_process_environment
from perfagent.stats import Aggregator

# k6's exit code when the script itself calls exec.test.abort().
_K6_SCRIPT_ABORTED = 108

_MAX_LOG_LINES = 1000   # keep the log buffer bounded


@dataclass
class RunState:
    run_id: str
    script_id: str
    tool: str
    target: str
    status: str = "starting"  # starting | preparing | running | finished | error | stopped
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    message: str = ""
    # the plan's LoadModel JSON, kept so the report can evaluate thresholds
    load_model_json: str = ""
    # optional test-data file to write next to the script (filename, content)
    data_filename: str = ""
    data_content: str = ""
    # live aggregated snapshot (computed deterministically)
    snapshot: dict = field(default_factory=dict)
    summary_metrics: dict | None = None
    run_start_ts: float | None = None
    run_end_ts: float | None = None
    # human-readable k6 output lines (console.*, thresholds, checks) — for live logs
    logs: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    _proc: subprocess.Popen | None = None
    _stop_requested: bool = False
    _deadline_reached: bool = False
    _log_secrets: tuple[str, ...] = ()
    _agg: Aggregator = field(default_factory=Aggregator)
    _tmpdir: str | None = None


# in-memory registry of runs
_RUNS: dict[str, RunState] = {}
_ACTIVE_RUNS: set[str] = set()
_RUNS_LOCK = threading.Lock()


class RunCapacityExceeded(RuntimeError):
    """Raised before a run is started when all execution slots are reserved."""


def get_run(run_id: str) -> RunState | None:
    return _RUNS.get(run_id)


def list_runs() -> list[RunState]:
    with _RUNS_LOCK:
        return sorted(_RUNS.values(), key=lambda r: r.started_at, reverse=True)


def k6_available() -> bool:
    """True if k6 is present, or can be fetched automatically on first run."""
    return k6_ready_or_provisionable()


def stop_run(run_id: str) -> bool:
    run = _RUNS.get(run_id)
    if run and run._proc and run.status == "running" and run._proc.poll() is None:
        run._stop_requested = True
        run._proc.terminate()
        return True
    return False


def start_run(
    run_id: str,
    script_id: str,
    tool: str,
    target: str,
    content: str,
    load_model_json: str = "",
    data_filename: str = "",
    data_content: str = "",
    metadata: dict | None = None,
) -> RunState:
    """Launch k6 for the given script content. Returns the RunState immediately;
    a background thread keeps parsing output and updating the snapshot."""
    run = RunState(run_id=run_id, script_id=script_id, tool=tool, target=target)
    run.load_model_json = load_model_json
    run._log_secrets = _request_log_secrets(load_model_json)
    run.data_filename = data_filename
    run.data_content = data_content
    run.metadata = dict(metadata or {})
    if tool != "k6":
        run.status = "error"
        run.message = f"live run is only implemented for k6 (got {tool!r})"
        run.ended_at = time.time()
        with _RUNS_LOCK:
            _RUNS[run_id] = run
        return run

    settings = get_settings()
    with _RUNS_LOCK:
        if len(_ACTIVE_RUNS) >= settings.perfagent_max_concurrent_runs:
            raise RunCapacityExceeded("All k6 run slots are busy. Wait for a run to finish and retry.")
        if run_id in _RUNS:
            raise ValueError("Run ID already exists.")
        _ACTIVE_RUNS.add(run_id)
        _RUNS[run_id] = run

    thread = threading.Thread(
        target=_run_with_limits, args=(run, content, settings.perfagent_max_run_seconds), daemon=True
    )
    try:
        thread.start()
    except RuntimeError:
        with _RUNS_LOCK:
            _ACTIVE_RUNS.remove(run_id)
            del _RUNS[run_id]
        raise
    return run


def _run_with_limits(run: RunState, content: str, max_seconds: int) -> None:
    try:
        _run_worker(run, content, max_seconds)
    except Exception:
        run.message = "The load runner could not complete this run."
        run.ended_at = time.time()
        run.status = "error"
    finally:
        try:
            if run._proc and run._proc.poll() is None:
                run._proc.kill()
                run._proc.wait()
        finally:
            if run._tmpdir:
                shutil.rmtree(run._tmpdir, ignore_errors=True)
            with _RUNS_LOCK:
                _ACTIVE_RUNS.remove(run.run_id)


def _expire_run(run: RunState, proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        run._deadline_reached = True
        proc.kill()


def _request_log_secrets(load_model_json: str) -> tuple[str, ...]:
    if not load_model_json:
        return ()
    try:
        model = json.loads(load_model_json)
    except (TypeError, ValueError):
        return ()
    headers = model.get("headers") if isinstance(model, dict) else None
    if not isinstance(headers, dict):
        return ()
    secrets = set()
    for header, value in headers.items():
        if not isinstance(value, str) or "${" in value:
            continue
        header = header.lower()
        if header in {"authorization", "proxy-authorization", "cookie", "x-api-key", "api-key", "x-auth-token"}:
            if value:
                secrets.add(value)
            if header in {"authorization", "proxy-authorization"} and " " in value:
                secrets.add(value.split(" ", 1)[1].strip())
            if header == "cookie":
                for cookie in value.split(";"):
                    if "=" in cookie:
                        secrets.add(cookie.split("=", 1)[1].strip())
    return tuple(sorted((value for value in secrets if value), key=len, reverse=True))


def _append_log(run: RunState, line: str) -> None:
    line = line.rstrip()
    if not line:
        return
    for secret in run._log_secrets:
        line = line.replace(secret, "<REDACTED>")
    identifiers: dict[str, str] = {}
    line = restore(redact_text(line, mapping=identifiers), identifiers)
    run.logs.append(line)
    if len(run.logs) > _MAX_LOG_LINES:
        del run.logs[: len(run.logs) - _MAX_LOG_LINES]


def _pump_stderr(run: RunState, proc: subprocess.Popen) -> None:
    """Read k6's stderr line by line into run.logs (console.*, thresholds, checks)."""
    if proc.stderr is None:
        return
    try:
        for line in proc.stderr:
            _append_log(run, line)
    except Exception:  # noqa: BLE001
        pass


def _run_worker(run: RunState, content: str, max_seconds: int) -> None:
    try:
        if find_k6() is None:
            run.status = "preparing"
            run.message = "Setting up the load engine (first run only)..."
        k6_path = ensure_k6()
    except K6Unavailable as e:
        run.status = "error"
        run.message = str(e)
        run.ended_at = time.time()
        return
    run.message = ""
    # Measure from when k6 actually starts, not from when the run was requested,
    # so a first-run download doesn't drag down the reported RPS.
    run._agg = Aggregator()

    tmpdir = tempfile.mkdtemp(prefix="perfagent_run_")
    run._tmpdir = tmpdir
    script_path = Path(tmpdir) / "loadtest.js"
    try:
        script_path.write_text(content, encoding="utf-8")
        if run.data_filename and run.data_content:
            filename = safe_runner_data_filename(run.data_filename)
            (Path(tmpdir) / filename).write_text(run.data_content, encoding="utf-8")
    except (ValueError, OSError) as exc:
        run.message = f"Could not prepare test inputs: {exc}"
        run.ended_at = time.time()
        run.status = "error"
        return

    # k6 --out json=- streams one JSON object per line to stdout.
    summary_path = Path(tmpdir) / "perfagent-summary.json"
    cmd = [k6_path, "run", "--address=", "--out", "json=-", "--quiet", "--summary-export",
           str(summary_path), str(script_path)]

    try:
        run.run_start_ts = time.time()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",      # k6 prints Unicode (█ ✓ µ); decode as UTF-8, not the
            errors="replace",      # OS default (cp1252 on Windows) which garbles them
            bufsize=1,
            cwd=tmpdir,
            env=k6_process_environment(tmpdir),
        )
    except Exception as e:  # noqa: BLE001
        run.message = f"failed to launch k6: {e}"
        run.status = "error"
        run.ended_at = time.time()
        return

    run._proc = proc
    run.status = "running"

    # Read k6's human output (console.*, thresholds, checks summary) in a thread,
    # so we don't block the metrics loop below. These feed the "Live run logs" panel.
    _append_log(run, f"$ k6 run loadtest.js  (target {run.target})")
    stderr_thread = threading.Thread(target=_pump_stderr, args=(run, proc), daemon=True)
    stderr_thread.start()

    timeout = threading.Timer(max_seconds, _expire_run, args=(run, proc))
    timeout.daemon = True
    timeout.start()
    try:
        _stream_metrics(run, proc)
        proc.wait()
    finally:
        timeout.cancel()
        timeout.join()
    run.run_end_ts = time.time()
    stderr_thread.join(timeout=2)
    try:
        metrics = json.loads(summary_path.read_text(encoding="utf-8"))["metrics"]
        if isinstance(metrics, dict):
            run.summary_metrics = metrics
    except (OSError, ValueError, KeyError, TypeError):
        pass
    run.snapshot = run._agg.snapshot()
    if run._deadline_reached:
        status = "stopped"
        run.message = f"The run stopped after reaching the {max_seconds}-second execution limit."
    elif run._stop_requested:
        status = "stopped"
    elif proc.returncode in (0, 99):
        # k6 exits 99 when an evaluated threshold fails.
        status = "finished"
    elif proc.returncode == _K6_SCRIPT_ABORTED:
        status = "stopped"
        reason = next((ln for ln in reversed(run.logs) if "Data file exhausted" in ln), "")
        run.message = (
            "The test stopped early: the data file ran out of rows (each row is "
            "used once). Add rows, or let rows repeat." if reason else
            "The script stopped the test early. See the run logs for the reason."
        )
    else:
        status = "error"
        run.message = f"k6 exited {proc.returncode}. See the run logs for details."
    _append_log(run, f"— k6 exited {proc.returncode} —")
    run.ended_at = run.run_end_ts
    run.status = status



def _stream_metrics(run: RunState, proc: subprocess.Popen) -> None:
    last_snapshot = 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Not a JSON metric point — treat as a human log line (defensive).
            _append_log(run, line)
            continue
        # k6 json output: {"type":"Point","metric":"http_req_duration","data":{...}}
        if obj.get("type") == "Point":
            run._agg.add_point(obj)
        # refresh the public snapshot at most ~4x/sec
        now = time.time()
        if now - last_snapshot > 0.25:
            run.snapshot = run._agg.snapshot()
            run.samples.append({"t": round(now - run.started_at, 2),
                                "rps": run.snapshot.get("rps", 0),
                                "p95": run.snapshot.get("latency", {}).get("p95_ms"),
                                "err": run.snapshot.get("error_rate", 0) * 100,
                                "dropped_iterations": run.snapshot.get("dropped_iterations")})
            if len(run.samples) > 1200:
                first_drop = next((index for index, sample in enumerate(run.samples)
                                   if sample.get("dropped_iterations")), None)
                run.samples = [sample for index, sample in enumerate(run.samples)
                               if index % 2 == 0 or index == first_drop]
            last_snapshot = now
