"""Tests for advanced correlation: array index, regex, nested paths."""

from __future__ import annotations

import pytest

from perfagent.contracts.load_model import (
    Extract, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.k6_renderer import render_k6


def _model(extract):
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="get", method="GET", path="/x", extract=[extract])])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_array_index_path():
    s = render_k6(_model(Extract(var="fid", source="json", path="data[0].id")))
    assert 'res.json("data.0.id")' in s


def test_nested_path():
    s = render_k6(_model(Extract(var="tok", source="json", path="result.session.token")))
    assert 'res.json("result.session.token")' in s


def test_regex_extraction():
    s = render_k6(_model(Extract(var="csrf", source="regex", path="csrf=([A-Za-z0-9]+)")))
    assert "new RegExp(" in s
    assert "_m_csrf[1]" in s


def test_regex_safe_on_no_match():
    s = render_k6(_model(Extract(var="x", source="regex", path="a=(\\d+)")))
    assert "vars.x = ''" in s          # falls back to empty if no match


def test_regex_source_accepted():
    Extract(var="x", source="regex", path="a=(.+)")   # should not raise


def test_invalid_source_rejected():
    with pytest.raises(Exception):
        Extract(var="x", source="xml", path="a")
