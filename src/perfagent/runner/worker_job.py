"""Launch k6 and its loopback adapter together inside a managed job namespace."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from perfagent.runner.process_environment import k6_process_environment
from perfagent.runner.worker_http import worker_http
from perfagent.runner.worker_protocol import MAX_SUMMARY_BYTES, WORKER_SUMMARY_TYPE


def run_worker_job(
    k6: Path, script: Path, bridge: Path, *, max_seconds: int, max_clients: int
) -> int:
    """Use the namespace's loopback adapter as the saved script's BASE_URL."""
    if max_seconds < 1:
        raise ValueError("A positive job deadline is required.")
    if not k6.is_absolute() or not script.is_absolute() or not bridge.is_absolute():
        raise ValueError("Use absolute paths for managed job inputs.")
    with tempfile.TemporaryDirectory(prefix="perfagent-job-") as scratch:
        summary = Path(scratch) / "summary.json"
        with worker_http(bridge, max_clients=max_clients, request_timeout=max_seconds) as endpoint:
            try:
                result = subprocess.run(
                    [
                        str(k6),
                        "run",
                        "--address=",
                        "--no-usage-report",
                        "--max-redirects=0",
                        "--out",
                        "json=-",
                        "--quiet",
                        "--summary-export",
                        str(summary),
                        "-e",
                        f"BASE_URL={endpoint}",
                        str(script),
                    ],
                    env=k6_process_environment(scratch),
                    cwd=script.parent,
                    timeout=max_seconds,
                    check=False,
                )
                if result.returncode in (0, 99):
                    _emit_summary(summary)
                return result.returncode
            except subprocess.TimeoutExpired:
                return 124


def _emit_summary(path: Path) -> None:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_SUMMARY_BYTES + 1)
        if len(raw) <= MAX_SUMMARY_BYTES:
            metrics = json.loads(raw).get("metrics")
            if isinstance(metrics, dict):
                print(json.dumps({"type": WORKER_SUMMARY_TYPE, "metrics": metrics}), flush=True)
    except (OSError, ValueError, AttributeError):
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k6", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--bridge", required=True, type=Path)
    parser.add_argument("--max-seconds", required=True, type=int)
    parser.add_argument("--max-clients", required=True, type=int)
    args = parser.parse_args()
    raise SystemExit(
        run_worker_job(
            args.k6,
            args.script,
            args.bridge,
            max_seconds=args.max_seconds,
            max_clients=args.max_clients,
        )
    )


if __name__ == "__main__":
    main()
