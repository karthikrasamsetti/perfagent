"""Prometheus series for PerfAgent runs.

Traffic series are grouped by scenario, environment, and load tool.
The active-run marker is removed when its run stops.
"""
from __future__ import annotations

from threading import Lock

import structlog
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram,
    generate_latest, CONTENT_TYPE_LATEST,
)

log = structlog.get_logger("perfagent.observability")

REGISTRY = CollectorRegistry()

# Mirror LoadModel.environment ("dev"/"staging"/"prod") and load_tool.
_LABELS = ["scenario", "environment", "load_tool"]

_SUMMARY_LOCK = Lock()
_SUMMARIES: dict[tuple[str, ...], dict[str, dict[str, float]]] = {}

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
        self._labels = tuple(self._base.values())

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
        with _SUMMARY_LOCK:
            runs = _SUMMARIES.setdefault(self._labels, {})
            summary = runs.setdefault(self.run_id, {})
            summary.update({key: value for key, value in (
                ("rps", rps), ("error_rate", error_rate), ("active_vus", active_vus),
            ) if value is not None})
            self._publish_summary(runs)

    def finish(self) -> None:
        with _SUMMARY_LOCK:
            runs = _SUMMARIES.get(self._labels, {})
            runs.pop(self.run_id, None)
            self._publish_summary(runs)
            if not runs:
                _SUMMARIES.pop(self._labels, None)
        RUN_ACTIVE.remove(*self._labels, self.run_id)

    def _publish_summary(self, runs: dict[str, dict[str, float]]) -> None:
        rps = sum(summary.get("rps", 0) for summary in runs.values())
        errors_per_second = sum(summary.get("error_rate", 0) * summary.get("rps", 0)
                                for summary in runs.values())
        RPS.labels(**self._base).set(rps)
        ERROR_RATE.labels(**self._base).set(errors_per_second / rps if rps else 0)
        VUS_ACTIVE.labels(**self._base).set(sum(summary.get("active_vus", 0) for summary in runs.values()))


def render_latest() -> tuple[bytes, str]:
    """Payload + content-type for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
