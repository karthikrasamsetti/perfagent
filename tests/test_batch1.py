"""Tests for Batch 1: trend endpoint + SLA profiles (API)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from perfagent.db import models as dbmodels
    dbmodels._engine = None
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    dbmodels.Base.metadata.create_all(eng)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    from perfagent.api import app as appmod
    return TestClient(appmod.app)


def test_trend_empty(client):
    r = client.get("/api/runs/trend")
    assert r.status_code == 200
    assert r.json()["points"] == []


def test_sla_create_list_delete(client):
    body = {"name": "API SLA", "thresholds": [
        {"metric": "p95_ms", "op": "<=", "value": 300},
        {"metric": "error_rate", "op": "<", "value": 0.01},
    ]}
    r = client.post("/api/sla", json=body)
    assert r.status_code == 200
    sid = r.json()["id"]

    lst = client.get("/api/sla").json()["profiles"]
    assert any(p["id"] == sid and p["name"] == "API SLA" for p in lst)
    prof = next(p for p in lst if p["id"] == sid)
    assert len(prof["thresholds"]) == 2

    d = client.delete(f"/api/sla/{sid}")
    assert d.status_code == 200
    assert all(p["id"] != sid for p in client.get("/api/sla").json()["profiles"])


def test_sla_name_required(client):
    r = client.post("/api/sla", json={"name": "  ", "thresholds": []})
    assert r.status_code == 400
