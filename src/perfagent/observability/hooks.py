"""Convert k6 points and run snapshots into Prometheus metrics."""
from __future__ import annotations

from .metrics import MetricsSink


def on_k6_point(sink: MetricsSink, point: dict) -> None:
    if point.get("metric") != "http_req_duration":
        return
    data = point.get("data", {})
    duration = data.get("value")
    if isinstance(duration, (int, float)) and duration >= 0:
        status = str((data.get("tags") or {}).get("status", ""))
        status_code = int(status) if status.isascii() and status.isdecimal() and len(status) <= 3 else 0
        sink.record_request(duration / 1000, status_code)


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
