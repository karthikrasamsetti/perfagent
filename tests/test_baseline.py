"""Tests for baseline / regression comparison."""

from __future__ import annotations

from perfagent.analyzer.baseline import compare, metrics_from_snapshot, no_baseline

_PREV = {"error_rate": 0.0, "p95_ms": 120, "p99_ms": 150, "avg_ms": 80, "rps": 10.0}


def test_regression_detected():
    cur = {"error_rate": 0.02, "p95_ms": 180, "p99_ms": 220, "avg_ms": 110, "rps": 8.5}
    r = compare(cur, _PREV)
    assert r["regressed"] is True
    p95 = next(d for d in r["deltas"] if d["metric"] == "p95_ms")
    assert p95["direction"] == "worse"
    assert round(p95["pct_change"], 2) == 0.50   # +50%


def test_improvement_not_regression():
    cur = {"error_rate": 0.0, "p95_ms": 110, "p99_ms": 140, "avg_ms": 78, "rps": 11.0}
    r = compare(cur, _PREV)
    assert r["regressed"] is False


def test_small_change_is_same():
    cur = {"error_rate": 0.0, "p95_ms": 122, "p99_ms": 151, "avg_ms": 81, "rps": 10.1}
    r = compare(cur, _PREV)
    assert r["regressed"] is False
    p95 = next(d for d in r["deltas"] if d["metric"] == "p95_ms")
    assert p95["direction"] == "same"   # under the 5% noise floor


def test_throughput_drop_is_regression():
    cur = {"error_rate": 0.0, "p95_ms": 120, "p99_ms": 150, "avg_ms": 80, "rps": 6.0}
    r = compare(cur, _PREV)
    rps = next(d for d in r["deltas"] if d["metric"] == "rps")
    assert rps["direction"] == "worse"   # lower rps is worse


def test_no_baseline_shape():
    nb = no_baseline()
    assert nb["has_previous"] is False
    assert nb["regressed"] is False


def test_metrics_from_snapshot():
    snap = {"requests": 100, "error_rate": 0.01, "rps": 5.0,
            "latency": {"p95_ms": 200, "p99_ms": 300, "avg_ms": 120}}
    m = metrics_from_snapshot(snap)
    assert m["requests"] == 100 and m["p95_ms"] == 200 and m["rps"] == 5.0
