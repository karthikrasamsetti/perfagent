"""Database layer: SQLite/Postgres connection handling, write-time safety, migrations.

Runs on SQLite by default. With PERFAGENT_TEST_DATABASE_URL set (see conftest.py) the
same tests run against Postgres, plus the Postgres-only ones at the bottom.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine  # redirected to Postgres by conftest when it is the target
from sqlalchemy.orm import Session

from perfagent.db import connection as dbconn
from perfagent.db import migrate
from perfagent.db.models import AuditRow, Base, PlanRow, ScriptRow, SlaProfileRow

PG_URL = os.environ.get("PERFAGENT_TEST_DATABASE_URL", "").strip()
postgres_only = pytest.mark.skipif(not PG_URL, reason="needs PERFAGENT_TEST_DATABASE_URL")


@pytest.fixture()
def empty_engine(tmp_path):
    """An empty database: a temp SQLite file, or a fresh schema on Postgres."""
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    yield eng
    eng.dispose()


@pytest.fixture()
def engine(empty_engine):
    migrate.prepare_database(empty_engine)
    return empty_engine


# ------------------------------------------------------------------- URLs ----

@pytest.mark.parametrize("url", [
    "postgresql://u:p@db.example:5432/perf",
    "postgres://u:p@db.example:5432/perf",
    "postgresql+psycopg://u:p@db.example:5432/perf",
    "postgresql+psycopg2://u:p@db.example:5432/perf",
])
def test_every_postgres_spelling_uses_psycopg3(url):
    parsed = dbconn.normalise_url(url)
    assert parsed.drivername == "postgresql+psycopg" and dbconn.is_postgres(url)
    assert parsed.host == "db.example" and parsed.database == "perf"


def test_default_and_sqlite_urls():
    assert dbconn.normalise_url("").drivername == "sqlite"
    assert dbconn.normalise_url(None).database == "perfagent.db"
    assert not dbconn.is_postgres("sqlite:///x.db")


def test_password_is_never_shown():
    url = "postgresql://perf:s3cr%40t@db.example/perf"
    assert "s3cr" not in dbconn.safe_url(url) and "***" in dbconn.safe_url(url)
    # the direct-connection form keeps it (and the special character stays encoded)
    assert dbconn.libpq_url(url) == "postgresql://perf:s3cr%40t@db.example/perf"


def test_engine_options_per_backend():
    pg = dbconn.build_engine("postgresql://u:p@127.0.0.1:1/x", pool_size=3)
    assert pg.dialect.name == "postgresql" and pg.dialect.driver == "psycopg"
    assert pg.pool.size() == 3 and pg.pool._pre_ping is True
    pg.dispose()
    lite = dbconn.build_engine("sqlite://")
    assert lite.dialect.name == "sqlite"
    lite.dispose()


def test_unreachable_database_fails_with_a_clear_message(monkeypatch):
    from perfagent import config
    from perfagent.db import models as dbmodels

    settings = config.Settings(
        _env_file=None, database_url="postgresql://perf:hunter2@127.0.0.1:1/nope")
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(dbmodels, "_engine", None)
    with pytest.raises(RuntimeError) as e:
        dbmodels.get_engine()
    msg = str(e.value)
    assert "DATABASE_URL" in msg and "127.0.0.1" in msg and "hunter2" not in msg
    assert dbmodels._engine is None                 # nothing half-initialised is kept


def test_get_engine_follows_the_setting(tmp_path, monkeypatch):
    from perfagent import config
    from perfagent.db import models as dbmodels

    path = tmp_path / "app.db"
    settings = config.Settings(_env_file=None, database_url=f"sqlite:///{path}")
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(dbmodels, "_engine", None)
    eng = dbmodels.get_engine()
    try:
        assert dbmodels.get_engine() is eng                         # created once
        assert migrate.current_revision(eng) == migrate.head_revision()
        assert "plans" in sa.inspect(eng).get_table_names()
    finally:
        eng.dispose()


# ------------------------------------------------------- write-time safety ----

def test_text_longer_than_its_column_is_trimmed_not_rejected(engine):
    """Postgres enforces VARCHAR(n); SQLite never did. A long value must not 500."""
    with Session(engine) as s:
        s.add(SlaProfileRow(name="n" * 500, thresholds_json="[]"))
        s.add(AuditRow(action="a" * 100, entity="e" * 100, entity_id="i" * 100,
                       target="t" * 2000, summary="s" * 5000, actor="x" * 500))
        s.commit()
        sla = s.query(SlaProfileRow).one()
        audit = s.query(AuditRow).one()
        assert len(sla.name) == 120
        assert (len(audit.action), len(audit.entity), len(audit.entity_id)) == (40, 20, 32)
        assert len(audit.target) == 500 and len(audit.actor) == 80
        assert len(audit.summary) == 5000                  # Text is unbounded: untouched


def test_updates_are_trimmed_too(engine):
    with Session(engine) as s:
        row = SlaProfileRow(name="ok", thresholds_json="[]")
        s.add(row)
        s.commit()
        row.name = "z" * 300
        s.commit()
        assert len(s.query(SlaProfileRow).one().name) == 120


def test_nul_bytes_are_removed(engine):
    """Postgres text cannot store \\x00 (it can turn up in uploaded files and logs)."""
    with Session(engine) as s:
        plan = PlanRow(target_base_url="http://x", goal="a\x00b", load_model_json='{"k":"v\x00"}')
        s.add(plan)
        s.flush()
        s.add(ScriptRow(plan_id=plan.id, tool="k6", filename="t\x00.js", content="x\x00y\x00"))
        s.commit()
        assert s.query(PlanRow).one().goal == "ab"
        script = s.query(ScriptRow).one()
        assert script.content == "xy" and script.filename == "t.js"


def test_timestamps_round_trip_as_naive_utc(engine):
    with Session(engine) as s:
        s.add(PlanRow(target_base_url="http://x", load_model_json="{}"))
        s.commit()
        created = s.query(PlanRow).one().created_at
    assert created.tzinfo is None
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - created).total_seconds()) < 60


# -------------------------------------------------------------- migrations ----

def test_new_database_gets_the_full_schema(empty_engine):
    assert sa.inspect(empty_engine).get_table_names() == []
    migrate.prepare_database(empty_engine)
    tables = set(sa.inspect(empty_engine).get_table_names())
    assert set(Base.metadata.tables) <= tables and "alembic_version" in tables
    assert migrate.current_revision(empty_engine) == migrate.head_revision() != ""
    migrate.prepare_database(empty_engine)                 # second start-up: no-op


def test_models_and_migrations_agree(engine):
    """If this fails you changed a model without writing a migration:
    uv run alembic revision --autogenerate -m "describe the change"."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"models differ from the migrated schema: {diff}"


def test_database_from_before_migrations_is_adopted_with_its_data(empty_engine):
    # how the app used to set a database up: create_all, no alembic_version table
    Base.metadata.create_all(empty_engine)
    with Session(empty_engine) as s:
        s.add(PlanRow(id="p" * 32, target_base_url="http://old", load_model_json="{}"))
        s.commit()
    assert migrate.current_revision(empty_engine) == ""

    migrate.prepare_database(empty_engine)

    assert migrate.current_revision(empty_engine) == migrate.head_revision()
    with Session(empty_engine) as s:
        assert s.get(PlanRow, "p" * 32).target_base_url == "http://old"


def test_partly_created_old_database_gets_its_missing_tables(empty_engine):
    Base.metadata.tables["plans"].create(empty_engine)      # only one table exists
    migrate.prepare_database(empty_engine)
    assert set(Base.metadata.tables) <= set(sa.inspect(empty_engine).get_table_names())


def test_instances_starting_together_do_not_collide(empty_engine):
    errors: list[Exception] = []

    def start():
        try:
            migrate.prepare_database(empty_engine)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=start) for _ in range(4)]
    if empty_engine.dialect.name != "postgresql":
        threads = threads[:1]            # SQLite: the app serialises this with a lock
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert errors == []
    assert migrate.current_revision(empty_engine) == migrate.head_revision()


def test_health_reports_the_database_in_use(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from perfagent.api import app as appmod
    from perfagent.db import models as dbmodels

    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: engine)
    j = TestClient(appmod.app).get("/api/health").json()
    assert j["status"] == "ok"
    assert j["database"]["backend"] == engine.dialect.name
    assert j["database"]["schema_up_to_date"] is True
    assert "password" not in str(j).lower()

    def broken(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(dbmodels, "get_engine", broken)
    assert TestClient(appmod.app).get("/api/health").status_code == 503


# ----------------------------------------------------------- Postgres only ----

@postgres_only
def test_pg_session_is_pinned_to_utc_whatever_the_server_default():
    eng = dbconn.build_engine(PG_URL)
    name = "tz_" + uuid.uuid4().hex[:10]
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    try:
        with eng.connect() as conn:
            # holds even when the database's own default zone is something else
            assert conn.execute(sa.text("SHOW timezone")).scalar().upper() in ("UTC", "ETC/UTC")
            conn.execute(sa.text(f'CREATE TEMP TABLE "{name}" (at timestamp)'))
            conn.execute(sa.text(f'INSERT INTO "{name}" VALUES (:at)'), {"at": aware})
            got = conn.execute(sa.text(f'SELECT at FROM "{name}"')).scalar()
            assert got == aware.replace(tzinfo=None)          # stored as naive UTC, unshifted
    finally:
        eng.dispose()


@postgres_only
def test_pg_enforces_the_plan_link_and_cascades_deletes(engine):
    from sqlalchemy.exc import IntegrityError
    with Session(engine) as s:
        s.add(ScriptRow(plan_id="missing", tool="k6", filename="x.js", content=""))
        with pytest.raises(IntegrityError):
            s.commit()
    with Session(engine) as s:
        plan = PlanRow(target_base_url="http://x", load_model_json="{}")
        plan.scripts.append(ScriptRow(tool="k6", filename="x.js", content=""))
        s.add(plan)
        s.commit()
        s.delete(plan)
        s.commit()
        assert s.query(ScriptRow).count() == 0


@postgres_only
def test_pg_chat_conversations_are_stored_in_postgres(engine, monkeypatch):
    """The LangGraph checkpoint store follows the main database."""
    from perfagent.chat import ChatService, ChatTurn, SessionNotFound
    from perfagent.chat_intent import ChatEndpoint, ChatIntent
    from perfagent.config import Settings
    from perfagent.db import models as dbmodels

    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: engine)
    schema = "c_" + uuid.uuid4().hex[:12]                     # isolate LangGraph's tables
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = dbconn.normalise_url(PG_URL).update_query_dict(
        {"options": f"-csearch_path={schema}"})
    settings = Settings(_env_file=None,
                        database_url=url.render_as_string(hide_password=False))

    class Provider:
        name = "fake"

        def structured(self, *, response_model, system, user):
            return ChatTurn(reply="ok", intent=ChatIntent(
                target_base_url="https://shop.test", endpoints=[ChatEndpoint(path="/login")]))

    try:
        first = ChatService(lambda: Provider(), settings=settings, retry_delay_seconds=0)
        sid = first.start("test login at https://shop.test")["session_id"]
        first.close()                                           # "restart"

        second = ChatService(lambda: Provider(), settings=settings, retry_delay_seconds=0)
        try:
            view = second.get(sid)
            assert view["status"] == "ready" and len(view["messages"]) == 2
            assert second.send(sid, "thanks")["turns"] == 2
            with engine.connect() as conn:
                n = conn.execute(sa.text(
                    f'SELECT count(*) FROM "{schema}".checkpoints WHERE thread_id = :t'),
                    {"t": sid}).scalar()
            assert n > 0                                        # really in Postgres
            second.delete(sid)
            with pytest.raises(SessionNotFound):
                second.get(sid)
        finally:
            second.close()
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
