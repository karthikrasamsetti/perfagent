"""Test configuration.

By default every test uses its own throw-away SQLite file — nothing to set up.

To run the WHOLE suite against a real Postgres instead (to prove the app behaves the
same there), point this variable at an empty database you can create schemas in:

    PERFAGENT_TEST_DATABASE_URL=postgresql://user:password@localhost:5432/perfagent_test
    uv run pytest -q -n auto

Each test's database then becomes its own schema in that Postgres database (dropped
again at the end), so tests stay isolated and can still run in parallel.
"""

from __future__ import annotations

import os
import uuid

import sqlalchemy

_PG_URL = os.environ.get("PERFAGENT_TEST_DATABASE_URL", "").strip()
_schemas: list[str] = []
_schema_for: dict[str, str] = {}

if _PG_URL:
    from sqlalchemy.pool import NullPool

    from perfagent.db.connection import normalise_url

    _real_create_engine = sqlalchemy.create_engine
    _pg = normalise_url(_PG_URL)

    def _create_engine(url, *args, **kwargs):
        """sqlite:///… in a test  ->  a fresh schema in the Postgres test database."""
        if not str(url).startswith("sqlite"):
            return _real_create_engine(url, *args, **kwargs)
        # The same SQLite path always maps to the same schema, exactly as the same
        # path is the same file: some fixtures open their database more than once.
        schema = _schema_for.get(str(url))
        if schema is None:
            schema = _schema_for[str(url)] = "t_" + uuid.uuid4().hex[:16]
            admin = _real_create_engine(_pg, poolclass=NullPool)
            with admin.begin() as conn:
                conn.execute(sqlalchemy.text(f'CREATE SCHEMA "{schema}"'))
            admin.dispose()
            _schemas.append(schema)
        return _real_create_engine(
            _pg, poolclass=NullPool,
            connect_args={"options": f"-c timezone=utc -c search_path={schema}"},
        )

    # Patched before any test module (or the app) imports create_engine.
    sqlalchemy.create_engine = _create_engine

    def pytest_sessionfinish(session, exitstatus):
        admin = _real_create_engine(_pg, poolclass=NullPool)
        with admin.begin() as conn:
            for schema in _schemas:
                conn.execute(sqlalchemy.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def pytest_report_header(config):
    if _PG_URL:
        from perfagent.db.connection import safe_url
        return f"perfagent database under test: {safe_url(_PG_URL)} (one schema per test)"
    return "perfagent database under test: SQLite (one temp file per test)"
