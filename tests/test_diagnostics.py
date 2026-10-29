"""Tests for the diagnostic analysis engine."""

from __future__ import annotations

from perfagent.analyzer.diagnostics import diagnose


def test_healthy_run_no_critical_findings():
    snap = {"error_rate": 0.0,
            "latency": {"avg_ms": 1.3, "p95_ms": 2.1, "p99_ms": 2.8, "max_ms": 4.0},
            "per_endpoint": [
                {"name": "Login", "requests": 10, "failed": 0, "avg_ms": 1.2, "p95_ms": 1.8},
                {"name": "Products", "requests": 40, "failed": 0, "avg_ms": 1.3, "p95_ms": 2.0}]}
    d = diagnose(snap, peak_users=5)
    sevs = {f.severity for f in d.findings}
    assert "high" not in sevs and "medium" not in sevs
    assert d.slowest_endpoint == "Products"


def test_errored_endpoint_flagged_high():
    snap = {"error_rate": 0.08,
            "latency": {"avg_ms": 50, "p95_ms": 600, "p99_ms": 900, "max_ms": 1200},
            "per_endpoint": [
                {"name": "Login", "requests": 100, "failed": 0, "avg_ms": 20, "p95_ms": 40},
                {"name": "Checkout", "requests": 100, "failed": 25, "avg_ms": 200, "p95_ms": 1800}]}
    d = diagnose(snap, peak_users=50)
    assert d.most_errored_endpoint == "Checkout"
    titles = [f.title for f in d.findings]
    assert any("failing often" in t for t in titles)
    assert d.findings[0].severity == "high"   # sorted: high first


def test_slow_endpoint_outlier_detected():
    snap = {"error_rate": 0.0,
            "latency": {"avg_ms": 50, "p95_ms": 500, "p99_ms": 700, "max_ms": 900},
            "per_endpoint": [
                {"name": "Fast", "requests": 100, "failed": 0, "avg_ms": 10, "p95_ms": 20},
                {"name": "Slow", "requests": 100, "failed": 0, "avg_ms": 400, "p95_ms": 900}]}
    d = diagnose(snap, peak_users=20)
    assert d.slowest_endpoint == "Slow"
    assert any("slower than the rest" in f.title for f in d.findings)


def test_long_tail_detected():
    snap = {"error_rate": 0.0,
            "latency": {"avg_ms": 100, "p95_ms": 200, "p99_ms": 1000, "max_ms": 1200},
            "per_endpoint": []}
    d = diagnose(snap, peak_users=10)
    assert any("latency tail" in f.title.lower() for f in d.findings)


def test_findings_sorted_by_severity():
    snap = {"error_rate": 0.08,
            "latency": {"avg_ms": 50, "p95_ms": 600, "p99_ms": 2400, "max_ms": 5000},
            "per_endpoint": [
                {"name": "A", "requests": 100, "failed": 0, "avg_ms": 10, "p95_ms": 20},
                {"name": "B", "requests": 100, "failed": 25, "avg_ms": 200, "p95_ms": 1800}]}
    d = diagnose(snap, peak_users=50)
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    sev_nums = [order[f.severity] for f in d.findings]
    assert sev_nums == sorted(sev_nums)


def test_to_dict_shape():
    snap = {"error_rate": 0.0, "latency": {"p95_ms": 2, "p99_ms": 3, "avg_ms": 1, "max_ms": 4},
            "per_endpoint": [{"name": "X", "requests": 5, "failed": 0, "p95_ms": 2}]}
    out = diagnose(snap, peak_users=3).to_dict()
    assert "headline" in out and "findings" in out
    assert isinstance(out["findings"], list)
