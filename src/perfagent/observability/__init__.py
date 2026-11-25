"""Deterministic observability layer: Prometheus metrics for live runs.

No LLM calls, no AI. Reads the same aggregated samples that already
drive the UI dashboard (stats/aggregator.py) and re-exposes them as
Prometheus series for Grafana. Classified x-access=read.
"""
from .metrics import MetricsSink, render_latest  # noqa: F401
