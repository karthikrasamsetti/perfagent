"""Tests for dynamic data generators in bodies/paths."""

from __future__ import annotations

from perfagent.contracts.load_model import (
    DataFile, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.generators import generator_js, is_generator
from perfagent.generator.k6_renderer import render_k6


def test_is_generator():
    assert is_generator("uuid")
    assert is_generator("randomInt(1,5)")
    assert is_generator("randomFrom(a,b)")
    assert not is_generator("username")      # a data column
    assert not is_generator("token")         # a correlation var


def test_generator_js_simple():
    assert generator_js("uuid") == "uuidv4()"
    assert generator_js("timestamp") == "Date.now()"
    assert generator_js("vu") == "__VU"


def test_generator_js_args():
    assert generator_js("randomInt(1,10)") == "(Math.floor(Math.random() * (10 - 1 + 1)) + 1)"
    assert ".slice(0,6)" in generator_js("randomString(6)")
    assert generator_js("randomFrom(a,b,c)") == '["a", "b", "c"][Math.floor(Math.random() * 3)]'


def _model(body=None, path="/x"):
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[Step(name="r", method="POST", path=path, body=body)])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_generators_render_in_body():
    s = render_k6(_model(body={"email": "${randomEmail}", "qty": "${randomInt(1,5)}"}))
    assert "@loadtest.test" in s
    assert "Math.floor(Math.random()" in s


def test_uuid_adds_import_and_renders_in_path():
    s = render_k6(_model(path="/orders/${uuid}", body={"x": 1}))
    assert "k6-utils" in s                    # import added
    assert "uuidv4()" in s


def test_no_generators_no_uuid_import():
    s = render_k6(_model(body={"x": "static"}))
    assert "k6-utils" not in s                 # no import when unused


# ---- regression tests for the two bugs ----

def test_uuid_import_present_with_headers():
    """Bug 1: uuid import must survive when headers are also declared."""
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/orders/${uuid}", body={"x": 1})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
        headers={"Authorization": "Bearer ${token}"},
    )
    s = render_k6(m)
    assert "k6-utils" in s           # import not overwritten by header decl
    assert "uuidv4()" in s


def test_orphan_field_no_data_file_is_safe():
    """Bug 2: ${field} with no data file must not emit row.field (which crashes)."""
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/login",
                 body={"user": "demo", "password": "${password}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "row.password" not in s   # no undefined-row crash
    assert '"password": \'\'' in s   # safe empty instead


def test_data_column_still_uses_row_when_file_present():
    """With a data file, ${column} must still resolve to row.column."""
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/x", body={"u": "${username}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
        data_file=DataFile(filename="u.csv", fields=["username"], source_format="csv"),
    )
    s = render_k6(m)
    assert "row.username" in s


# ---- realistic generators + Postman {{var}} syntax ----

def test_realistic_generators_render():
    from perfagent.generator.generators import generator_js
    assert generator_js("randomFullName") == "fakeName()"
    assert generator_js("randomCompanyName") == "fakeCompany()"
    assert generator_js("randomCatchPhrase") == "fakeCatchPhrase()"
    assert generator_js("randomBic") == "fakeBic()"


def test_date_offset():
    from perfagent.generator.generators import generator_js
    js = generator_js("dateOffset(3,'days')")
    assert "3 * 86400000" in js
    assert "toISOString()" in js


def test_faker_helpers_emitted_when_used():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/x",
                 body={"contact": "${randomFullName}", "company": "${randomCompanyName}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "function fakeName()" in s      # helper block emitted
    assert "fakeName()" in s


def test_postman_double_brace_syntax():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/x",
                 body={"name": "{{$randomFullName}}", "email": "{{$randomEmail}}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "fakeName()" in s               # {{$randomFullName}} -> fakeName()
    assert "@loadtest.test" in s           # {{$randomEmail}} -> email generator


def test_no_faker_helpers_when_unused():
    m = LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="r", method="POST", path="/x", body={"x": "${uuid}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "function fakeName()" not in s  # not emitted when no realistic generator used
