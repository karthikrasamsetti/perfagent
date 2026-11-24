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

def test_nested_k6_summary_keeps_custom_metrics_and_reports_measured_values():
    from perfagent.analyzer.verdict import evaluate_k6_summary
    from perfagent.ci.jenkins import summarize_k6

    metrics = {
        "http_req_duration": {"values": {"p(95)": 230}, "thresholds": {"p(95)<500": {"ok": True}}},
        "http_reqs": {"values": {"count": 1000, "rate": 15}},
        "http_req_failed": {"values": {"rate": .02}, "thresholds": {"rate<0.01": {"ok": False}}},
        "checks{check:response is XML}": {"values": {"rate": 1}, "thresholds": {"rate>=0.99": {"ok": True}}},
    }

    result = evaluate_k6_summary(metrics)
    assert result["overall_passed"] is False
    assert [(c["metric"], c["actual"], c["passed"]) for c in result["checks"]] == [
        ("p95_ms", 230, True), ("error_rate", .02, False), ("checks{check:response is XML} rate", 1, True),
    ]
    archived = summarize_k6({"metrics": metrics})
    assert archived["requests"] == 1000
    assert archived["rps"] == 15
    assert archived["p95_ms"] == 230
    assert archived["error_rate"] == .02
    assert archived["verdict"] == "fail"
