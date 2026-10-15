"""Tests for correlation — extract a value from a response, reuse it in later steps."""

from __future__ import annotations

from perfagent.contracts.load_model import (
    DataFile,
    Extract,
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.generator.k6_renderer import render_k6


def _profile():
    return LoadProfile(type=LoadProfileType.RAMP, stages=[Stage(duration_seconds=5, target_users=3)])


def _balanced(s):
    return s.count("{") == s.count("}") and s.count("(") == s.count(")")


def test_extract_captures_value():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="auth", steps=[
            Step(name="login", method="POST", path="/login", body={"u": "x"},
                 extract=[Extract(var="token", source="json", path="token")]),
            Step(name="me", method="GET", path="/me"),
        ])],
        load_profile=_profile(),
        headers={"Authorization": "Bearer ${token}"},
    )
    s = render_k6(m)
    assert _balanced(s)
    assert "let vars = {}" in s
    assert 'vars.token = res.json("token")' in s
    assert "DYN_HEADERS" in s                 # token used in a dynamic header


def test_extract_used_in_path():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="order", steps=[
            Step(name="create", method="POST", path="/orders", body={"i": 1},
                 extract=[Extract(var="order_id", source="json", path="id")]),
            Step(name="get", method="GET", path="/orders/${order_id}"),
        ])],
        load_profile=_profile(),
    )
    s = render_k6(m)
    assert "vars.order_id = res.json" in s
    assert "/orders/${vars.order_id}" in s     # captured id used in the path


def test_no_correlation_is_clean():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="b", steps=[Step(name="v", method="GET", path="/products")])],
        load_profile=_profile(),
    )
    s = render_k6(m)
    assert "vars" not in s
    assert "DYN_HEADERS" not in s
    assert "const HEADERS" not in s


def test_static_headers_still_work():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="b", steps=[Step(name="v", method="GET", path="/products")])],
        load_profile=_profile(),
        headers={"X-Api-Key": "static123"},
    )
    s = render_k6(m)
    assert "const HEADERS =" in s
    assert "DYN_HEADERS" not in s
    assert "headers: HEADERS" in s


def test_data_and_correlation_together():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="mix", steps=[
            Step(name="login", method="POST", path="/login", body={"user": "${username}"},
                 extract=[Extract(var="tok", source="json", path="token")]),
            Step(name="buy", method="POST", path="/buy/${product_id}", body={"auth": "${tok}"}),
        ])],
        load_profile=_profile(),
        data_file=DataFile(filename="u.csv", fields=["username", "product_id"], source_format="csv"),
    )
    s = render_k6(m)
    assert _balanced(s)
    assert "row.username" in s      # data column -> row.*
    assert "vars.tok" in s          # captured var -> vars.*


def test_extract_var_must_be_identifier():
    import pytest
    with pytest.raises(Exception):
        Extract(var="not an identifier", path="token")
