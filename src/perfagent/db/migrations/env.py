"""Alembic environment for PerfAgent.

Used two ways:
  - by the app at start-up (perfagent/db/migrate.py passes in its own connection);
  - from the command line (`uv run alembic ...`), where the database comes from the
    DATABASE_URL setting, exactly as the app reads it.
"""

from __future__ import annotations

from alembic import context

from perfagent.db.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite cannot ALTER most things in place; batch mode rebuilds the table.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)                      # the app's connection; it commits
else:
    from perfagent.config import get_settings
    from perfagent.db.connection import build_engine

    engine = build_engine(get_settings().database_url)
    with engine.connect() as conn:
        _run(conn)
        conn.commit()
    engine.dispose()
