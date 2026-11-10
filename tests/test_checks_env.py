"""Tests for the new assertion kinds, env/TLS, and check-suggestion schema."""

from __future__ import annotations

from perfagent.check_suggest import (
    SuggestedCheck, SuggestedChecks, build_check_suggest_prompt,
)
from perfagent.contracts.load_model import (
    Assertion, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.k6_renderer import render_k6


def _model(assertions=None, insecure=False):
    return LoadModel(
        target_base_url="https://x.com", insecure_tls=insecure,
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="GET", path="/x", assertions=assertions or [])])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_not_contains():
    s = render_k6(_model([Assertion(kind="not_contains", value="Invalid")]))
    assert '!(r.body && r.body.includes("Invalid"))' in s


def test_response_time():
    s = render_k6(_model([Assertion(kind="response_time", value="2000")]))
    assert "r.timings.duration < 2000" in s


def test_insecure_tls_flag():
    assert "insecureSkipTLSVerify: true" in render_k6(_model(insecure=True))
    assert "insecureSkipTLSVerify" not in render_k6(_model(insecure=False))


def test_environment_field():
    m = _model()
    m.environment = "staging"
    assert m.environment == "staging"   # carried on the model


def test_not_contains_kind_valid():
    Assertion(kind="not_contains", value="x")       # should not raise
    Assertion(kind="response_time", value="1000")   # should not raise


def test_suggested_checks_schema():
    sc = SuggestedChecks(checks=[
        SuggestedCheck(kind="body_contains", value="<Rate>", reason="rate element present"),
        SuggestedCheck(kind="not_contains", value="<Error>", reason="no error"),
        SuggestedCheck(kind="json_path", op="gt", path="total", value="0", reason="positive total"),
    ])
    assert len(sc.checks) == 3
    assert sc.checks[0].kind == "body_contains"


def test_suggest_prompt_includes_sample():
    p = build_check_suggest_prompt("<OnTracRateResponse><Rate>...</Rate></OnTracRateResponse>")
    assert "OnTracRateResponse" in p
    assert "validation checks" in p.lower()
