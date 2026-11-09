"""Tests for Batch 3: tracing + GraphQL."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from perfagent.contracts.load_model import (
    Assertion, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.k6_renderer import render_k6


# ---- GraphQL ----

def test_graphql_body_shape():
    m = LoadModel(
        target_base_url="https://api.x.com",
        scenarios=[Scenario(name="g", steps=[
            Step(name="q", method="POST", path="/graphql",
                 graphql_query="query($id: ID!) { user(id: $id) { name } }",
                 body={"id": "5"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "query:" in s and "variables:" in s
    assert "/graphql" in s


def test_graphql_generators_in_variables():
    m = LoadModel(
        target_base_url="https://api.x.com",
        scenarios=[Scenario(name="g", steps=[
            Step(name="q", method="POST", path="/graphql",
                 graphql_query="query { x }",
                 body={"id": "${randomInt(1,100)}"})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "Math.floor(Math.random()" in s


def test_non_graphql_unchanged():
    m = LoadModel(
        target_base_url="https://api.x.com",
        scenarios=[Scenario(name="g", steps=[
            Step(name="q", method="POST", path="/x", body={"a": 1})])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )
    s = render_k6(m)
    assert "query:" not in s   # plain POST, no graphql wrapping


# ---- Tracing ----

@pytest.fixture()
def _db(tmp_path, monkeypatch):
    from perfagent.db import models as dbmodels
    dbmodels._engine = None
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    dbmodels.Base.metadata.create_all(eng)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    yield


def test_trace_record_and_recent(_db):
    from perfagent import tracing
    tracing.record(step="plan", model="gpt-4o", prompt_tokens=1000,
                   completion_tokens=200, latency_ms=2000, status="ok", redactions=1)
    tracing.record(step="dynamize", model="gpt-4o", prompt_tokens=500,
                   completion_tokens=100, latency_ms=1500, status="ok")
    tr = tracing.recent()
    assert len(tr) == 2
    assert tr[0]["step"] == "dynamize"         # newest first
    assert tr[1]["latency_ms"] == 2000
    assert tr[1]["total_tokens"] == 1200


def test_trace_records_error(_db):
    from perfagent import tracing
    tracing.record(step="chat", model="gpt-4o", prompt_tokens=0,
                   completion_tokens=0, latency_ms=300, status="error", error="Timeout")
    tr = tracing.recent()
    assert tr[0]["status"] == "error"
    assert "Timeout" in tr[0]["error"]


def test_set_step_context():
    from perfagent import tracing
    tracing.set_step("narrate")
    assert tracing.current_step() == "narrate"
