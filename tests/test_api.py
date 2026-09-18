"""API tests — drive the FastAPI app with a fake provider and a temp database."""

from __future__ import annotations

import importlib
from typing import TypeVar

import pytest
from pydantic import BaseModel

from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)

T = TypeVar("T", bound=BaseModel)


def _canned_model() -> LoadModel:
    return LoadModel(
        target_base_url="http://127.0.0.1:8000",
        scenarios=[
            Scenario(name="browse", weight=0.8, steps=[Step(name="list", path="/products")]),
            Scenario(
                name="checkout",
                weight=0.2,
                steps=[Step(name="pay", method="POST", path="/checkout", body={"pay": "card"})],
            ),
        ],
        load_profile=LoadProfile(
            type=LoadProfileType.RAMP,
            stages=[Stage(duration_seconds=60, target_users=50)],
        ),
    )


class FakeProvider:
    name = "fake"

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        return _canned_model()  # type: ignore[return-value]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the DB at a temp file so tests don't touch the real one.
    from perfagent.db import models as dbmodels

    dbmodels._engine = None  # reset cached engine
    db_url = f"sqlite:///{tmp_path/'test.db'}"
    monkeypatch.setattr(dbmodels, "get_engine", lambda *_a, **_k: _make_engine(db_url))

    # Import the app fresh and stub the provider factory.
    from perfagent.api import app as appmod
    importlib.reload(appmod)
    monkeypatch.setattr(appmod, "build_provider", lambda *_a, **_k: FakeProvider())

    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def _make_engine(db_url):
    from sqlalchemy import create_engine

    from perfagent.db.models import Base
    eng = create_engine(db_url)
    Base.metadata.create_all(eng)
    return eng


def _plan_body():
    return {
        "target_base_url": "http://127.0.0.1:8000",
        "goal": "test",
        "max_users": 100,
        "duration_seconds": 240,
        "endpoints": [
            {"method": "GET", "path": "/products"},
            {"method": "POST", "path": "/checkout"},
        ],
    }


def test_tools_endpoint(client):
    r = client.get("/api/tools")
    assert r.status_code == 200
    assert r.json()["tools"][0] == "k6"


def test_index_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Performance Testing Agent" in r.text


def test_plan_then_generate_flow(client):
    # 1. draft a plan
    r = client.post("/api/plan", json=_plan_body())
    assert r.status_code == 200, r.text
    plan_id = r.json()["plan_id"]
    assert r.json()["load_model"]["scenarios"][0]["name"] == "browse"

    # 2. generate a k6 script from it
    r2 = client.post(f"/api/plan/{plan_id}/generate", json={"tool": "k6"})
    assert r2.status_code == 200, r2.text
    assert "import http from 'k6/http'" in r2.json()["content"]
    script_id = r2.json()["script_id"]

    # 3. it's saved and listed with lineage
    r3 = client.get(f"/api/plans/{plan_id}")
    assert r3.status_code == 200
    assert len(r3.json()["scripts"]) == 1

    # 4. download works
    r4 = client.get(f"/api/scripts/{script_id}/download")
    assert r4.status_code == 200
    assert "k6/http" in r4.text


def test_generate_with_edited_model(client):
    r = client.post("/api/plan", json=_plan_body())
    plan_id = r.json()["plan_id"]
    edited = r.json()["load_model"]
    edited["scenarios"][0]["name"] = "edited_browse"

    r2 = client.post(f"/api/plan/{plan_id}/generate", json={"tool": "k6", "load_model": edited})
    assert r2.status_code == 200
    # the edit persisted
    r3 = client.get(f"/api/plans/{plan_id}")
    names = [s["name"] for s in r3.json()["load_model"]["scenarios"]]
    assert "edited_browse" in names


def test_unknown_tool_rejected(client):
    r = client.post("/api/plan", json=_plan_body())
    plan_id = r.json()["plan_id"]
    r2 = client.post(f"/api/plan/{plan_id}/generate", json={"tool": "jmeter"})
    assert r2.status_code == 400
