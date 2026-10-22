"""Tests for planner sanity fixes: duplicate journeys and nonsensical thresholds."""

from __future__ import annotations

from pydantic import BaseModel

from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
    Threshold,
)
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.spec import EndpointSpec


class _Fake:
    name = "fake"

    def __init__(self, model):
        self._m = model

    def structured(self, *, response_model, system, user):
        return self._m


def _req():
    return PlanRequest(
        target_base_url="http://127.0.0.1:8001",
        max_users=3, duration_seconds=10,
        endpoints=[EndpointSpec(method="POST", path="/login")],
    )


def _profile():
    return LoadProfile(type=LoadProfileType.RAMP, stages=[Stage(duration_seconds=5, target_users=3)])


def test_duplicate_journeys_are_merged():
    # Two "journeys" that both just hit /login -> should collapse to one.
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[
            Scenario(name="Browsing", weight=0.8, steps=[Step(name="l", method="POST", path="/login")]),
            Scenario(name="Checkout", weight=0.2, steps=[Step(name="l", method="POST", path="/login")]),
        ],
        load_profile=_profile(),
    )
    plan = draft_plan(_req(), _Fake(model))
    assert len(plan.load_model.scenarios) == 1
    assert plan.load_model.scenarios[0].weight == 1.0   # weights summed


def test_distinct_journeys_are_kept():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[
            Scenario(name="Browse", weight=0.7, steps=[Step(name="v", method="GET", path="/products")]),
            Scenario(name="Checkout", weight=0.3, steps=[
                Step(name="l", method="POST", path="/login"),
                Step(name="p", method="POST", path="/checkout")]),
        ],
        load_profile=_profile(),
    )
    plan = draft_plan(_req(), _Fake(model))
    assert len(plan.load_model.scenarios) == 2   # genuinely different -> both kept


def test_nonsensical_error_threshold_fixed():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[Step(name="l", method="POST", path="/login")])],
        load_profile=_profile(),
        thresholds=[Threshold(metric="error_rate", op="<", value=1.0)],   # 100% = meaningless
    )
    plan = draft_plan(_req(), _Fake(model))
    er = next(t for t in plan.load_model.thresholds if t.metric == "error_rate")
    assert er.value == 0.05   # fixed to 5%


def test_zero_latency_threshold_fixed():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[Step(name="v", method="GET", path="/products")])],
        load_profile=_profile(),
        thresholds=[Threshold(metric="p95_ms", op="<=", value=0)],   # <= 0ms impossible
    )
    plan = draft_plan(_req(), _Fake(model))
    p95 = next(t for t in plan.load_model.thresholds if t.metric == "p95_ms")
    assert p95.value == 500.0


def test_missing_thresholds_get_defaults():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[Step(name="v", method="GET", path="/products")])],
        load_profile=_profile(),
        thresholds=[],
    )
    plan = draft_plan(_req(), _Fake(model))
    metrics = {t.metric for t in plan.load_model.thresholds}
    assert "error_rate" in metrics and "p95_ms" in metrics
