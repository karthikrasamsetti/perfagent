"""Tests for the Planner — using a fake provider so no real API calls are made.

The fake provider returns a canned LoadModel, letting us test the Planner's logic
(prompt building, guard-rail enforcement, lineage) fast, free, and deterministically.
"""

from __future__ import annotations

from typing import TypeVar

import pytest
from pydantic import BaseModel

from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.planner import EndpointSpec, PlanRequest, draft_plan
from perfagent.planner.prompts import build_user_prompt

T = TypeVar("T", bound=BaseModel)


class FakeProvider:
    """Returns a preset LoadModel and records what it was asked."""

    name = "fake"

    def __init__(self, model: LoadModel) -> None:
        self._model = model
        self.last_system: str | None = None
        self.last_user: str | None = None

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        self.last_system = system
        self.last_user = user
        assert response_model is LoadModel
        return self._model  # type: ignore[return-value]


def _request() -> PlanRequest:
    return PlanRequest(
        target_base_url="http://127.0.0.1:8000",
        goal="test browsing and checkout",
        max_users=100,
        duration_seconds=240,
        endpoints=[
            EndpointSpec(method="GET", path="/products"),
            EndpointSpec(method="POST", path="/checkout", example_body={"pay": "card"}),
        ],
    )


def _canned_model(target="http://example.com", peak=50, total=180) -> LoadModel:
    return LoadModel(
        target_base_url=target,
        scenarios=[
            Scenario(name="browse", weight=0.8, steps=[Step(name="list", path="/products")]),
            Scenario(
                name="checkout",
                weight=0.2,
                steps=[Step(name="pay", method="POST", path="/checkout", body={"pay": "card"})],
            ),
        ],
        load_profile=LoadProfile(
            type=LoadProfileType.RAMP,
            stages=[Stage(duration_seconds=total, target_users=peak)],
        ),
    )


def test_endpoint_spec_path_validation():
    with pytest.raises(ValueError):
        EndpointSpec(method="GET", path="products")


def test_plan_request_url_validation():
    with pytest.raises(ValueError):
        PlanRequest(
            target_base_url="ftp://x",
            endpoints=[EndpointSpec(path="/a")],
        )


def test_prompt_lists_all_endpoints():
    prompt = build_user_prompt(_request())
    assert "/products" in prompt
    assert "/checkout" in prompt
    assert "http://127.0.0.1:8000" in prompt
    assert "max_users=100" in prompt


def test_draft_plan_returns_artifact_with_lineage():
    provider = FakeProvider(_canned_model())
    plan = draft_plan(_request(), provider)
    assert plan.id  # has identity
    assert plan.load_model.scenarios[0].name == "browse"
    # provider was actually invoked with our prompts
    assert provider.last_user is not None
    assert "/products" in provider.last_user


def test_guardrail_forces_target_url():
    # The canned model has the WRONG target; the planner must overwrite it.
    provider = FakeProvider(_canned_model(target="http://wrong.example"))
    plan = draft_plan(_request(), provider)
    assert plan.load_model.target_base_url == "http://127.0.0.1:8000"


def test_guardrail_clamps_max_users():
    # Canned model wants 500 users; request caps at 100.
    provider = FakeProvider(_canned_model(peak=500))
    plan = draft_plan(_request(), provider)
    assert plan.load_model.load_profile.peak_users == 100


def test_guardrail_clamps_duration():
    # Canned model wants 1000s; request caps at 240.
    provider = FakeProvider(_canned_model(total=1000))
    plan = draft_plan(_request(), provider)
    assert plan.load_model.load_profile.total_seconds <= 240


def test_planned_model_flows_into_generator():
    """The whole point: a drafted plan renders with the unchanged Phase-1 generator."""
    import ast

    from perfagent.generator import generate_script

    provider = FakeProvider(_canned_model())
    plan = draft_plan(_request(), provider)
    script = generate_script(plan, tool="locust")
    assert script.plan_id == plan.id
    ast.parse(script.content)  # still valid Python
