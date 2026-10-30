"""Tests for header/cookie correlation extraction."""

from __future__ import annotations

import pytest

from perfagent.contracts.load_model import (
    Extract,
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.generator.k6_renderer import render_k6


def _model(extract):
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="auth", steps=[
            Step(name="login", method="POST", path="/login", extract=[extract]),
            Step(name="me", method="GET", path="/me"),
        ])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_json_extraction():
    s = render_k6(_model(Extract(var="tok", source="json", path="token")))
    assert 'res.json("token")' in s


def test_header_extraction():
    s = render_k6(_model(Extract(var="tok", source="header", path="X-Auth-Token")))
    assert 'res.headers["X-Auth-Token"]' in s


def test_cookie_extraction():
    s = render_k6(_model(Extract(var="tok", source="cookie", path="session")))
    assert 'res.cookies["session"]' in s
    assert ".value" in s


def test_invalid_source_rejected():
    with pytest.raises(Exception):
        Extract(var="tok", source="xml", path="token")
