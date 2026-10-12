"""Tests for the AI evaluation harness — plan grounding and report citation checks."""

from __future__ import annotations

from perfagent.evaluation import evaluate_plan, evaluate_report
from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    Scenario,
    Stage,
    Step,
    Threshold,
)
from perfagent.planner.spec import EndpointSpec, PlanRequest


def _request():
    return PlanRequest(
        target_base_url="http://127.0.0.1:8000",
        max_users=100,
        duration_seconds=240,
        endpoints=[
            EndpointSpec(method="GET", path="/products"),
            EndpointSpec(method="POST", path="/checkout"),
        ],
    )


def _good_model():
    return LoadModel(
        target_base_url="http://127.0.0.1:8000",
        scenarios=[
            Scenario(name="browse", weight=0.8, steps=[Step(name="v", path="/products")]),
            Scenario(name="checkout", weight=0.2,
                     steps=[Step(name="c", method="POST", path="/checkout", body={})]),
        ],
        load_profile=LoadProfile(stages=[
            Stage(duration_seconds=48, target_users=100),
            Stage(duration_seconds=144, target_users=100),
            Stage(duration_seconds=48, target_users=0),
        ]),
        thresholds=[Threshold(metric="p95_ms", op="<", value=500)],
    )


# ---- plan evaluation ----

def test_good_plan_is_fully_grounded():
    ev = evaluate_plan(_good_model(), _request())
    assert ev.grounded
    assert ev.score == 1.0


def test_invented_endpoint_is_caught():
    m = _good_model()
    m.scenarios[0].steps.append(Step(name="bad", path="/admin/secret"))  # not supplied
    ev = evaluate_plan(m, _request())
    assert not ev.grounded
    names = {c.name: c for c in ev.checks}
    assert names["no_invented_endpoints"].passed is False
    assert "/admin/secret" in names["no_invented_endpoints"].detail


def test_wrong_target_is_caught():
    m = _good_model()
    m.target_base_url = "http://evil.example"
    ev = evaluate_plan(m, _request())
    names = {c.name: c for c in ev.checks}
    assert names["target_matches_request"].passed is False


def test_guardrail_breach_is_caught():
    m = _good_model()
    m.load_profile.stages[0].target_users = 5000  # exceeds max_users=100
    ev = evaluate_plan(m, _request())
    names = {c.name: c for c in ev.checks}
    assert names["within_guardrails"].passed is False


def test_summary_shape():
    ev = evaluate_plan(_good_model(), _request())
    s = ev.summary()
    assert s["grounded"] is True
    assert s["passed"] == s["total"]
    assert isinstance(s["checks"], list)


# ---- report evaluation ----

def _snapshot():
    return {
        "requests": 220, "failed": 0, "error_rate": 0.0, "rps": 2.49,
        "latency": {"avg_ms": 1.28, "p50_ms": 1.2, "p90_ms": 1.7,
                    "p95_ms": 1.67, "p99_ms": 1.82, "max_ms": 1.87},
        "per_endpoint": [],
    }


def _verdict():
    return {"overall_passed": True, "checks": [
        {"metric": "p95_ms", "op": "<=", "target": 500, "actual": 1.67, "passed": True},
        {"metric": "error_rate", "op": "<=", "target": 0.01, "actual": 0.0, "passed": True},
    ]}


def test_faithful_report_passes():
    text = ("The test passed. 220 requests at 2.49 requests/sec, 0.00% errors, "
            "p95 latency 1.67 ms, well under the 500 ms threshold.")
    ev = evaluate_report(text, _snapshot(), _verdict())
    assert ev.grounded
    assert ev.hallucinated == 0


def test_hallucinated_number_is_caught():
    # 999 appears nowhere in the metrics — a fabricated figure
    text = "The system handled 220 requests but latency spiked to 999 ms at peak."
    ev = evaluate_report(text, _snapshot(), _verdict())
    assert not ev.grounded
    assert "999" in ev.unsupported_numbers


def test_percentile_labels_allowed():
    text = "We report p50, p90, p95 and p99 percentiles."
    ev = evaluate_report(text, _snapshot(), _verdict())
    assert ev.grounded  # 50/90/95/99 are always-ok labels