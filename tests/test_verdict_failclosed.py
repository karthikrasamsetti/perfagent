"""Tests for the fail-closed verdict — unknown/missing metrics never PASS."""

from __future__ import annotations

from perfagent.analyzer.verdict import evaluate
from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    Scenario,
    Stage,
    Step,
    Threshold,
)


def _model(thresholds):
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[Step(name="v", path="/products")])],
        load_profile=LoadProfile(stages=[Stage(duration_seconds=10, target_users=5)]),
        thresholds=thresholds,
    )


_SNAP = {
    "error_rate": 0.0,
    "latency": {"p95_ms": 120.0, "p99_ms": 150.0, "avg_ms": 90.0, "p50_ms": 80.0, "max_ms": 200.0},
}


def test_all_known_and_pass():
    m = _model([Threshold(metric="p95_ms", op="<=", value=500),
                Threshold(metric="error_rate", op="<=", value=0.01)])
    assert evaluate(m, _SNAP)["overall_passed"] is True


def test_known_fail():
    m = _model([Threshold(metric="p95_ms", op="<=", value=50)])
    assert evaluate(m, _SNAP)["overall_passed"] is False


def test_unknown_metric_is_inconclusive_not_pass():
    # A passing known threshold alongside an UNKNOWN one must NOT yield PASS.
    m = _model([Threshold(metric="p95_ms", op="<=", value=500),
                Threshold(metric="throughput_tps", op=">=", value=100)])
    v = evaluate(m, _SNAP)
    assert v["overall_passed"] is None          # fail-closed
    assert v["has_unevaluable"] is True
    bad = [c for c in v["checks"] if c["passed"] is None]
    assert bad and "unknown metric" in bad[0]["reason"]


def test_missing_metric_is_inconclusive():
    snap = {"latency": {"p95_ms": 120.0}}        # no error_rate present
    m = _model([Threshold(metric="error_rate", op="<=", value=0.01)])
    v = evaluate(m, snap)
    assert v["overall_passed"] is None


def test_no_thresholds_is_inconclusive():
    m = _model([])
    assert evaluate(m, _SNAP)["overall_passed"] is None