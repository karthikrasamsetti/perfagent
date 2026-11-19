"""Prometheus series for PerfAgent runs.

Cardinality rule: run_id is NOT a Prometheus label (high-cardinality,
would bloat the TSDB). Per-run detail lives in the run_records table and
is queried through perfagent.reporting. Live series are grouped by the
low-cardinality (scenario, environment, load_tool) tuple that already
exists on LoadModel.
"""
from __future__ import annotations

import structlog
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram,
    generate_latest, CONTENT_TYPE_LATEST,
)

log = structlog.get_logger("perfagent.observability")

REGISTRY = CollectorRegistry()

# Mirror LoadModel.environment ("dev"/"staging"/"prod") and load_tool.
_LABELS = ["scenario", "environment", "load_tool"]

REQUESTS_TOTAL = Counter(
    "perfagent_requests_total", "Requests issued during runs",
    _LABELS + ["status_class"], registry=REGISTRY,
)
REQUEST_DURATION = Histogram(
    "perfagent_request_duration_seconds", "Per-request latency",
    _LABELS,
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    registry=REGISTRY,
)
VUS_ACTIVE = Gauge(
    "perfagent_vus_active", "Active virtual users", _LABELS,
    registry=REGISTRY,
)
ERROR_RATE = Gauge(
    "perfagent_error_rate", "Rolling error rate 0..1 "
    "(includes failed assertions, per aggregator policy)",
    _LABELS, registry=REGISTRY,
)
RPS = Gauge(
    "perfagent_rps", "Requests per second", _LABELS, registry=REGISTRY,
)
RUN_ACTIVE = Gauge(
    "perfagent_run_active", "1 while a run is executing",
    _LABELS + ["run_id"], registry=REGISTRY,
)


class MetricsSink:
    """Adapter from aggregator snapshots to Prometheus series.

    One instance per run. The k6_runner already produces a running
    summary via stats/aggregator.py; call update_summary() on each
    streamed snapshot so Prometheus scrapes reflect the run in near
    real time.
    """

    def __init__(self, *, scenario: str, environment: str,
                 load_tool: str, run_id: str) -> None:
        self._base = {
            "scenario": scenario,
            "environment": environment or "unspecified",
            "load_tool": load_tool,
        }
        self.run_id = run_id

    def mark_active(self, active: bool = True) -> None:
        RUN_ACTIVE.labels(**self._base, run_id=self.run_id).set(
            1 if active else 0)

    def record_request(self, duration_s: float, status_code: int) -> None:
        REQUESTS_TOTAL.labels(
            **self._base, status_class=f"{status_code // 100}xx").inc()
        REQUEST_DURATION.labels(**self._base).observe(duration_s)

    def update_summary(self, *, rps: float | None = None,
                       error_rate: float | None = None,
                       active_vus: int | None = None) -> None:
        """Push an aggregator summary snapshot into the gauges."""
        if rps is not None:
            RPS.labels(**self._base).set(rps)
        if error_rate is not None:
            ERROR_RATE.labels(**self._base).set(error_rate)
        if active_vus is not None:
            VUS_ACTIVE.labels(**self._base).set(active_vus)


def render_latest() -> tuple[bytes, str]:
    """Payload + content-type for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
