"""Tests for uploading and running an existing (hand-written) script."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _make_engine(url):
    from perfagent.db import models as dbmodels
    eng = create_engine(url)
    dbmodels.Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from perfagent.db import models as dbmodels
    dbmodels._engine = None
    db_url = f"sqlite:///{tmp_path/'test.db'}"
    eng = _make_engine(db_url)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    monkeypatch.setattr(Session, "__init__", Session.__init__)
    from perfagent.api import app as appmod
    return TestClient(appmod.app)


def test_upload_script_creates_runnable_script(client):
    body = {
        "filename": "my.js",
        "content": "import http from 'k6/http'; export default function(){ http.get('http://x'); }",
        "target_base_url": "http://127.0.0.1:8000",
        "tool": "k6",
    }
    r = client.post("/api/scripts/upload", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["script_id"]
    assert j["tool"] == "k6"
    assert j["filename"] == "my.js"
    # the script is now downloadable like any other
    dl = client.get(f"/api/scripts/{j['script_id']}/download")
    assert dl.status_code == 200
    assert "k6/http" in dl.text


def test_upload_empty_rejected(client):
    r = client.post("/api/scripts/upload", json={"content": "   "})
    assert r.status_code == 400


def test_upload_unknown_tool_rejected(client):
    r = client.post("/api/scripts/upload",
                    json={"content": "x", "tool": "notatool"})
    assert r.status_code == 400
