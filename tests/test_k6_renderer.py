"""Tests for the k6 renderer (the primary tool)."""

from __future__ import annotations

import pytest

from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
    ThinkTime,
    Threshold,
)
from perfagent.generator import DEFAULT_TOOL, generate_script, render, supported_tools


@pytest.mark.parametrize(("executor", "options", "expected"), [
    ("constant-vus", {}, ["vus: 1", "duration: '6s'"]),
    ("shared-iterations", {"iterations": 12}, ["iterations: 9", "iterations: 3", "maxDuration: '6s'"]),
    ("per-vu-iterations", {"iterations": 5}, ["iterations: 5", "maxDuration: '6s'"]),
    ("ramping-arrival-rate", {"start_rate": 0, "rate_stages": [
        {"duration_seconds": 3, "target_rate": 10}, {"duration_seconds": 3, "target_rate": 0},
    ]}, ["startRate: 0", "preAllocatedVUs:", "timeUnit: '1s'", "target: 0"]),
])
def test_guided_executor_schedules(executor, options, expected):
    from perfagent.runner.k6_binary import find_k6
    from perfagent.runner.validator import validate_script

    model = _model()
    model.load_profile = LoadProfile.model_validate({
        "stages": [{"duration_seconds": 6, "target_users": 4}],
        "executor_options": {"executor": executor, **options},
    })
    content = render(model, "k6")[1]
    assert content.count(f"executor: '{executor}'") == len(model.scenarios)
    assert all(option in content for option in expected)
    if find_k6():
        result = validate_script(content)
        assert result["ok"], result


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
        thresholds=[
            Threshold(metric="p95_ms", op="<", value=500),
            Threshold(metric="error_rate", op="<", value=0.01),
        ],
    )


def test_k6_is_default_and_first():
    assert DEFAULT_TOOL == "k6"
    assert supported_tools()[0] == "k6"
    assert "locust" in supported_tools()


def test_render_k6_returns_js():
    filename, content = render(_model(), tool="k6")
    assert filename == "loadtest.js"
    assert "import http from 'k6/http'" in content
    assert "export const options" in content


def test_k6_contains_scenarios_and_steps():
    _, content = render(_model())  # default k6
    assert "ramping-vus" in content
    assert "/products" in content
    assert "/checkout" in content
    assert "http.get(" in content
    assert "http.post(" in content


def test_k6_thresholds_mapped():
    _, content = render(_model())
    assert "http_req_duration" in content
    assert "p(95)<500" in content
    assert "rate<0.01" in content


def test_k6_stages_scaled_by_weight():
    # Peak 100 users, browse weight 0.7 -> ~70 target in browse scenario.
    _, content = render(_model())
    assert "target: 70" in content  # browse gets 70% of 100
    assert "target: 30" in content  # checkout gets 30%


def test_k6_determinism():
    a = render(_model())[1]
    b = render(_model())[1]
    assert a == b


def test_k6_lineage():
    plan = PlanArtifact(load_model=_model())
    script = generate_script(plan, tool="k6")
    assert script.plan_id == plan.id
    assert script.tool == "k6"
    assert script.filename == "loadtest.js"


def test_weighted_stage_targets_sum_to_requested_peak():
    from perfagent.generator.k6_renderer import _allocate_users

    assert _allocate_users(15, [0.7, 0.3]) == [11, 4]
    assert _allocate_users(0, [0.7, 0.3]) == [0, 0]


def test_literal_template_characters_are_escaped_while_placeholders_still_work():
    from perfagent.generator.k6_corr import body_expr, headers_expr, path_expr

    literal = '/example/`${literal part}/${id}'
    escaped = r'/example/\`\${literal part}/${vars.id}'
    assert path_expr(literal, {"id"}) == escaped
    assert escaped in body_expr({"nested": [literal]}, {"id"})
    assert escaped in headers_expr({"Example": literal}, {"id"})
