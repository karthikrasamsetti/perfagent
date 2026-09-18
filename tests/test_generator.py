"""Tests for the deterministic Locust generator and artifact lineage."""

from __future__ import annotations

import ast

import pytest

from perfagent.contracts import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    PlanArtifact,
    Scenario,
    Stage,
    Step,
    ThinkTime,
)
from perfagent.generator import generate_script, render, supported_tools


def _model() -> LoadModel:
    return LoadModel(
        target_base_url="http://127.0.0.1:8000",
        scenarios=[
            Scenario(
                name="browse products",
                weight=0.7,
                steps=[Step(name="view products", method="GET", path="/products")],
                think_time=ThinkTime(min_seconds=1, max_seconds=4),
            ),
            Scenario(
                name="checkout flow",
                weight=0.3,
                steps=[
                    Step(name="login", method="POST", path="/login", body={"user": "demo"}),
                    Step(name="checkout", method="POST", path="/checkout", body={"pay": "card"}),
                ],
            ),
        ],
        load_profile=LoadProfile(
            type=LoadProfileType.RAMP,
            stages=[
                Stage(duration_seconds=60, target_users=20),
                Stage(duration_seconds=120, target_users=100),
                Stage(duration_seconds=60, target_users=0),
            ],
        ),
    )


def test_supported_tools_includes_locust():
    assert "locust" in supported_tools()


def test_unknown_tool_raises():
    with pytest.raises(ValueError):
        render(_model(), tool="notatool")  # genuinely unsupported


def test_render_returns_filename_and_content():
    filename, content = render(_model(), tool="locust")
    assert filename == "locustfile.py"
    assert "from locust import" in content


def test_generated_script_is_valid_python():
    """The most important test: the rendered Locust file must parse as Python."""
    _, content = render(_model(), tool="locust")
    ast.parse(content)  # raises SyntaxError if the template produced junk


def test_generated_script_contains_expected_pieces():
    _, content = render(_model(), tool="locust")
    # both scenarios rendered as HttpUser classes
    assert "class BrowseProducts(HttpUser):" in content
    assert "class CheckoutFlow(HttpUser):" in content
    # steps rendered
    assert 'self.client.get("/products"' in content
    assert 'self.client.post(' in content
    assert '"/checkout"' in content
    # the load shape is present with cumulative timing
    assert "class GeneratedLoadShape(LoadTestShape):" in content
    assert '"duration": 60' in content
    assert '"duration": 180' in content
    assert '"duration": 240' in content


def test_determinism_same_input_same_output():
    m = _model()
    _, a = render(m, tool="locust")
    _, b = render(m, tool="locust")
    assert a == b


def test_lineage_preserved():
    plan = PlanArtifact(load_model=_model())
    script = generate_script(plan, tool="locust")
    assert script.plan_id == plan.id
    assert script.tool == "locust"
    assert script.filename == "locustfile.py"
