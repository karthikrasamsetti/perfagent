"""Test that generated scripts log on check/request failure (for live logs)."""

from __future__ import annotations

from perfagent.contracts.load_model import (
    Assertion, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.k6_renderer import render_k6


def _model():
    return LoadModel(
        target_base_url="https://x.com",
        scenarios=[Scenario(name="s", steps=[
            Step(name="get rates", method="GET", path="/rates",
                 assertions=[Assertion(kind="not_contains", value="Invalid")])])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_logs_on_failure():
    s = render_k6(_model())
    assert "console.error" in s
    assert "[FAIL][VU" in s
    assert "get rates" in s          # the step name is in the log


def test_logs_include_status_and_body():
    s = render_k6(_model())
    assert "status ${res.status}" in s
    assert "body:" in s              # a short body preview is logged


def test_no_log_without_failure_path():
    # the log is guarded by the failure condition, not unconditional
    s = render_k6(_model())
    assert "if (res.status >= 400 || !ok) {" in s
