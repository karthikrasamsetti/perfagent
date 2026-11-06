"""Test that real request bodies are restored into the plan (no <FIELD_REDACTED> leak)."""

from __future__ import annotations

from perfagent.contracts.load_model import (
    LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.spec import EndpointSpec


class _Fake:
    name = "fake"

    def __init__(self, model):
        self._m = model

    def structured(self, *, response_model, system, user):
        return self._m


def _profile():
    return LoadProfile(type=LoadProfileType.RAMP, stages=[Stage(duration_seconds=5, target_users=3)])


def test_redacted_body_is_restored():
    # AI returns a plan with the redacted value (as happens because it only saw redacted input)
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[
            Step(name="login", method="POST", path="/login",
                 body={"user": "demo", "password": "<FIELD_REDACTED>"})])],
        load_profile=_profile(),
    )
    req = PlanRequest(
        target_base_url="http://127.0.0.1:8000", max_users=3, duration_seconds=20,
        endpoints=[EndpointSpec(method="POST", path="/login",
                                example_body={"user": "demo", "password": "RealPass123"})],
    )
    plan = draft_plan(req, _Fake(model))
    body = plan.load_model.scenarios[0].steps[0].body
    assert body["password"] == "RealPass123"
    assert "<FIELD_REDACTED>" not in str(plan.load_model.model_dump())


def test_generators_preserved():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[
            Step(name="signup", method="POST", path="/signup",
                 body={"email": "${randomEmail}"})])],
        load_profile=_profile(),
    )
    req = PlanRequest(
        target_base_url="http://x:8000", max_users=3, duration_seconds=20,
        endpoints=[EndpointSpec(method="POST", path="/signup",
                                example_body={"email": "${randomEmail}"})],
    )
    plan = draft_plan(req, _Fake(model))
    assert plan.load_model.scenarios[0].steps[0].body["email"] == "${randomEmail}"


def test_unmatched_step_body_left_intact():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="s", steps=[
            Step(name="x", method="POST", path="/unlisted", body={"x": 1})])],
        load_profile=_profile(),
    )
    req = PlanRequest(
        target_base_url="http://x:8000", max_users=3, duration_seconds=20,
        endpoints=[EndpointSpec(method="GET", path="/products")],
    )
    plan = draft_plan(req, _Fake(model))
    assert plan.load_model.scenarios[0].steps[0].body == {"x": 1}
