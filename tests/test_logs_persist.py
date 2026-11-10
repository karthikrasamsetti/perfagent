"""Tests for persisted run logs in the report payload and logs download."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from perfagent.db import models as dbmodels
    dbmodels._engine = None
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    dbmodels.Base.metadata.create_all(eng)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    from perfagent.api import app as appmod
    return TestClient(appmod.app)


def test_run_state_has_logs():
    from perfagent.runner.k6_runner import RunState
    r = RunState(run_id="r", script_id="s", tool="k6", target="http://x")
    assert r.logs == []


def test_append_log_bounds_and_skips_empty():
    from perfagent.runner.k6_runner import RunState, _append_log
    r = RunState(run_id="r", script_id="s", tool="k6", target="http://x")
    _append_log(r, "line 1  ")
    _append_log(r, "")            # skipped
    _append_log(r, "line 2")
    assert r.logs == ["line 1", "line 2"]
    for i in range(2000):
        _append_log(r, f"x{i}")
    assert len(r.logs) <= 1000    # bounded


def test_logs_download_404_when_none(client):
    r = client.get("/api/runs/nonexistent/logs/download")
    assert r.status_code == 404
