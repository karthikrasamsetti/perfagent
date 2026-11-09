"""Tests for response assertions rendered into k6 checks."""

from __future__ import annotations

import pytest

from perfagent.contracts.load_model import (
    Assertion, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.k6_renderer import render_k6


def _model(assertions):
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="get", method="GET", path="/orders/1", assertions=assertions)])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_status_assertion():
    s = render_k6(_model([Assertion(kind="status", op="eq", value="200")]))
    assert "r.status === 200" in s


def test_json_path_eq():
    s = render_k6(_model([Assertion(kind="json_path", op="eq", path="status", value="ok")]))
    assert 'r.json("status")' in s
    assert '"ok"' in s


def test_json_path_gt_numeric():
    s = render_k6(_model([Assertion(kind="json_path", op="gt", path="total", value="0")]))
    assert 'Number(r.json("total")) > 0' in s


def test_body_contains():
    s = render_k6(_model([Assertion(kind="body_contains", value="orderId")]))
    assert 'includes("orderId")' in s


def test_failed_assertion_counts_as_error():
    s = render_k6(_model([Assertion(kind="status", op="eq", value="200")]))
    assert "const ok = check(res" in s
    assert "!ok" in s          # a failed check raises the error rate


def test_no_assertions_still_works():
    s = render_k6(_model([]))
    assert "check(res" in s     # base status check still present


def test_invalid_kind_rejected():
    with pytest.raises(Exception):
        Assertion(kind="magic", op="eq", value="x")
