"""Tests for the LoadModel contract — validation is the trust boundary."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from perfagent.contracts import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
    ThinkTime,
    Threshold,
)


def _minimal_model() -> LoadModel:
    return LoadModel(
        target_base_url="http://localhost:8000",
        scenarios=[Scenario(name="s", steps=[Step(name="get", path="/x")])],
        load_profile=LoadProfile(stages=[Stage(duration_seconds=10, target_users=5)]),
    )


def test_minimal_model_is_valid():
    m = _minimal_model()
    assert m.target_base_url == "http://localhost:8000"
    assert m.load_profile.peak_users == 5
    assert m.load_profile.total_seconds == 10


def test_url_must_be_http():
    with pytest.raises(ValidationError):
        LoadModel(
            target_base_url="localhost:8000",
            scenarios=[Scenario(name="s", steps=[Step(name="g", path="/x")])],
            load_profile=LoadProfile(stages=[Stage(duration_seconds=1, target_users=1)]),
        )


def test_url_trailing_slash_stripped():
    m = LoadModel(
        target_base_url="http://localhost:8000/",
        scenarios=[Scenario(name="s", steps=[Step(name="g", path="/x")])],
        load_profile=LoadProfile(stages=[Stage(duration_seconds=1, target_users=1)]),
    )
    assert m.target_base_url == "http://localhost:8000"


def test_path_must_start_with_slash():
    with pytest.raises(ValidationError):
        Step(name="bad", path="products")


def test_scenario_requires_at_least_one_step():
    with pytest.raises(ValidationError):
        Scenario(name="empty", steps=[])


def test_think_time_order_enforced():
    with pytest.raises(ValidationError):
        ThinkTime(min_seconds=5, max_seconds=1)


def test_threshold_operator_validated():
    Threshold(metric="p95_ms", op="<", value=100)  # ok
    with pytest.raises(ValidationError):
        Threshold(metric="p95_ms", op="!!", value=100)


def test_weights_normalise():
    m = LoadModel(
        target_base_url="http://localhost",
        scenarios=[
            Scenario(name="a", weight=3, steps=[Step(name="g", path="/a")]),
            Scenario(name="b", weight=1, steps=[Step(name="g", path="/b")]),
        ],
        load_profile=LoadProfile(stages=[Stage(duration_seconds=1, target_users=1)]),
    )
    weights = m.normalised_weights()
    assert weights == [0.75, 0.25]
    assert abs(sum(weights) - 1.0) < 1e-9


def test_profile_types_available():
    assert {t.value for t in LoadProfileType} == {"ramp", "spike", "soak", "stress"}
