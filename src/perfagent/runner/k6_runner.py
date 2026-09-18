"""The Runner: execute a k6 script as a subprocess and stream live metrics.

Design (matches the trust boundary):
  - k6 does the load and emits raw per-request metrics as JSON lines.
  - This module PARSES and AGGREGATES those deterministically in Python — every
    number the UI shows (RPS, error rate, p95) is computed here, in code, not by
    an LLM.
  - Runs are tracked in memory by run_id; the API polls get_run() for live status.

k6 must be installed and on PATH. If it isn't, the run is marked 'error' with a
clear message rather than crashing the server.
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

from perfagent.stats import Aggregator


@dataclass
class RunState:
    run_id: str
    script_id: str
    tool: str
    target: str
    status: str = "starting"  # starting | running | finished | error | stopped
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    message: str = ""
    # the plan's LoadModel JSON, kept so the report can evaluate thresholds
    load_model_json: str = ""
    # live aggregated snapshot (computed deterministically)
    snapshot: dict = field(default_factory=dict)
    _proc: subprocess.Popen | None = None
    _agg: Aggregator = field(default_factory=Aggregator)
    _tmpdir: str | None = None


# in-memory registry of runs
_RUNS: dict[str, RunState] = {}


def get_run(run_id: str) -> RunState | None:
    return _RUNS.get(run_id)


def list_runs() -> list[RunState]:
    return sorted(_RUNS.values(), key=lambda r: r.started_at, reverse=True)


def k6_available() -> bool:
    return shutil.which("k6") is not None


def stop_run(run_id: str) -> bool:
    run = _RUNS.get(run_id)
    if run and run._proc and run.status == "running":
        run._proc.terminate()
        run.status = "stopped"
        run.ended_at = time.time()
        return True
    return False


def start_run(
    run_id: str,
    script_id: str,
    tool: str,
    target: str,
    content: str,
    load_model_json: str = "",
) -> RunState:
    """Launch k6 for the given script content. Returns the RunState immediately;
    a background thread keeps parsing output and updating the snapshot."""
    run = RunState(run_id=run_id, script_id=script_id, tool=tool, target=target)
    run.load_model_json = load_model_json
    _RUNS[run_id] = run

    if tool != "k6":
        run.status = "error"
        run.message = f"live run is only implemented for k6 (got {tool!r})"
        run.ended_at = time.time()
        return run

    if not k6_available():
        run.status = "error"
        run.message = "k6 is not installed or not on PATH. Install k6 to run tests."
        run.ended_at = time.time()
        return run

    thread = threading.Thread(target=_run_worker, args=(run, content), daemon=True)
    thread.start()
    return run


def _run_worker(run: RunState, content: str) -> None:
    tmpdir = tempfile.mkdtemp(prefix="perfagent_run_")
    run._tmpdir = tmpdir
    script_path = Path(tmpdir) / "loadtest.js"
    script_path.write_text(content, encoding="utf-8")

    # k6 --out json=- streams one JSON object per line to stdout.
    cmd = ["k6", "run", "--out", "json=-", "--quiet", str(script_path)]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=tmpdir,
        )
    except Exception as e:  # noqa: BLE001
        run.status = "error"
        run.message = f"failed to launch k6: {e}"
        run.ended_at = time.time()
        return

    run._proc = proc
    run.status = "running"

    last_snapshot = 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # k6 json output: {"type":"Point","metric":"http_req_duration","data":{...}}
        if obj.get("type") == "Point":
            run._agg.add_point(obj)
        # refresh the public snapshot at most ~4x/sec
        now = time.time()
        if now - last_snapshot > 0.25:
            run.snapshot = run._agg.snapshot()
            last_snapshot = now

    proc.wait()
    run.snapshot = run._agg.snapshot()
    if run.status != "stopped":
        run.status = "finished" if proc.returncode in (0, 99) else "error"
        # k6 exits 99 when a threshold fails — that's a completed run, not a crash.
        if proc.returncode not in (0, 99):
            err = proc.stderr.read() if proc.stderr else ""
            run.message = f"k6 exited {proc.returncode}. {err[:400]}"
    run.ended_at = time.time()