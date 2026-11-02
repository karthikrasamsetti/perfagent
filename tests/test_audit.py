"""Tests for the audit trail."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    from perfagent.db import models as dbmodels
    from sqlalchemy import create_engine
    dbmodels._engine = None
    eng = create_engine(f"sqlite:///{tmp_path/'audit.db'}")
    dbmodels.Base.metadata.create_all(eng)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    yield


def test_record_and_recent():
    from perfagent import audit
    audit.record("plan.created", entity="plan", entity_id="p1",
                 target="http://x", summary="drafted")
    audit.record("run.started", entity="run", entity_id="r1",
                 target="http://x", summary="peak 50 VUs")
    ev = audit.recent(limit=10)
    assert len(ev) == 2
    assert ev[0]["action"] == "run.started"      # newest first
    assert ev[1]["action"] == "plan.created"
    assert ev[0]["summary"] == "peak 50 VUs"


def test_recent_respects_limit():
    from perfagent import audit
    for i in range(5):
        audit.record("run.started", entity="run", entity_id=f"r{i}", summary=str(i))
    assert len(audit.recent(limit=3)) == 3


def test_record_never_raises_on_db_error(monkeypatch):
    from perfagent import audit
    # even if the DB write fails, record() must not raise (best-effort)
    monkeypatch.setattr(audit, "get_session", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    audit.record("run.started", entity="run", entity_id="x")  # should not raise
