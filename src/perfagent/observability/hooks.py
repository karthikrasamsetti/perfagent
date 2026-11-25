"""Wire MetricsSink into the existing k6 run loop with minimal coupling.

k6_runner.py already streams metric snapshots to the UI. These helpers
let it also feed Prometheus without the runner importing prometheus
directly -- pass the hook callbacks in, keep the runner tool-agnostic.
"""
from __future__ import annotations

from typing import Protocol

from .metrics import MetricsSink


class RunContext(Protocol):
    run_id: str
    scenario: str
    environment: str
    load_tool: str


def sink_for(ctx: RunContext) -> MetricsSink:
    """Create and activate a sink for a run context."""
    sink = MetricsSink(
        scenario=ctx.scenario, environment=ctx.environment,
        load_tool=ctx.load_tool, run_id=ctx.run_id,
    )
    sink.mark_active(True)
    return sink


def on_aggregator_snapshot(sink: MetricsSink, snapshot: dict) -> None:
    """Map a stats/aggregator.py summary dict onto Prometheus series.

    Expects the summary shape the aggregator already produces:
    {"rps": float, "error_rate": float, "active_vus": int, ...}.
    """
    sink.update_summary(
        rps=snapshot.get("rps"),
        error_rate=snapshot.get("error_rate"),
        active_vus=snapshot.get("active_vus"),
    )
