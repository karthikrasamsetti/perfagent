"""Test that the planner auto-adds the Authorization header when a token is captured."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from perfagent.contracts.load_model import (
    Extract,
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.spec import EndpointSpec

T = TypeVar("T", bound=BaseModel)


class _Fake:
    name = "fake"

    def __init__(self, model):
        self._m = model

    def structured(self, *, response_model, system, user):
        return self._m


def _req():
    return PlanRequest(
        target_base_url="http://127.0.0.1:8001",
        max_users=5, duration_seconds=60,
        endpoints=[EndpointSpec(method="POST", path="/login"),
                   EndpointSpec(method="GET", path="/me")],
    )


def test_auto_header_added_when_token_captured():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="auth", steps=[
            Step(name="login", method="POST", path="/login", body={"u": "x"},
                 extract=[Extract(var="token", source="json", path="token")]),
            Step(name="me", method="GET", path="/me"),
        ])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=5)]),
    )
    plan = draft_plan(_req(), _Fake(model))
    assert plan.load_model.headers.get("Authorization") == "Bearer ${token}"
    assert plan.load_model.target_base_url == "http://127.0.0.1:8001"


def test_no_header_added_without_token():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="browse", steps=[Step(name="v", method="GET", path="/products")])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=5)]),
    )
    plan = draft_plan(_req(), _Fake(model))
    assert "Authorization" not in plan.load_model.headers


def test_existing_auth_header_not_overwritten():
    model = LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="auth", steps=[
            Step(name="login", method="POST", path="/login",
                 extract=[Extract(var="token", source="json", path="token")]),
        ])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=5)]),
        headers={"Authorization": "Bearer custom"},
    )
    plan = draft_plan(_req(), _Fake(model))
    assert plan.load_model.headers["Authorization"] == "Bearer custom"
