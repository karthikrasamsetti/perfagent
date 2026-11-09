"""The Runner: execute a k6 script as a subprocess and stream live metrics.

Design (matches the trust boundary):
  - k6 does the load and emits raw per-request metrics as JSON lines.
  - This module PARSES and AGGREGATES those deterministically in Python — every
    number the UI shows (RPS, error rate, p95) is computed here, in code, not by
    an LLM.
  - Runs are tracked in memory by run_id; the API polls get_run() for live status.
  - If the script is data-parameterized, the uploaded data file is written next to
    the script so k6's open('./file') finds it.

k6 does NOT need to be installed by the customer: k6_binary.ensure_k6() finds a
bundled/cached copy or downloads the pinned, checksum-verified release on first run.
If that fails (e.g. offline), the run is marked 'error' with a clear message.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from perfagent.runner.k6_binary import K6Unavailable, ensure_k6, find_k6, k6_ready_or_provisionable
from perfagent.stats import Aggregator


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
    """True if k6 is present, or can be fetched automatically on first run."""
    return k6_ready_or_provisionable()


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
    data_filename: str = "",
    data_content: str = "",
) -> RunState:
    """Launch k6 for the given script content. Returns the RunState immediately;
    a background thread keeps parsing output and updating the snapshot."""
    run = RunState(run_id=run_id, script_id=script_id, tool=tool, target=target)
    run.load_model_json = load_model_json
    run.data_filename = data_filename
    run.data_content = data_content
    _RUNS[run_id] = run

    if tool != "k6":
        run.status = "error"
        run.message = f"live run is only implemented for k6 (got {tool!r})"
        run.ended_at = time.time()
        return run

    thread = threading.Thread(target=_run_worker, args=(run, content), daemon=True)
    thread.start()
    return run


def _run_worker(run: RunState, content: str) -> None:
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
    script_path.write_text(content, encoding="utf-8")

    # If the script is data-parameterized, place the data file beside it so
    # k6's open('./<file>') resolves (we run k6 with cwd=tmpdir).
    if run.data_filename and run.data_content:
        (Path(tmpdir) / run.data_filename).write_text(run.data_content, encoding="utf-8")

    # k6 --out json=- streams one JSON object per line to stdout.
    cmd = [k6_path, "run", "--out", "json=-", "--quiet", str(script_path)]

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