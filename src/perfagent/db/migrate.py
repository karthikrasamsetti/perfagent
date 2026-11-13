"""Bring the database schema up to date (Alembic), automatically on start-up.

The app calls ``prepare_database(engine)`` the first time it opens the database:

  - a brand-new database (SQLite or Postgres) gets every table;
  - a database from before migrations existed is adopted as it is;
  - a database that is behind gets the migrations it is missing.

So there is nothing to run by hand when deploying. When you CHANGE a model, write a
migration for it (see alembic.ini) — tests/test_database.py fails if the models and
the migrations disagree.

On Postgres the work is wrapped in an advisory lock, so several app instances
starting at the same moment don't migrate at the same time.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Any fixed number; it only has to be the same for every PerfAgent instance.
_ADVISORY_LOCK_KEY = 7342_0001


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def head_revision() -> str:
    """The newest migration the code knows about."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head() or ""


def current_revision(engine: Engine) -> str:
    """The migration the database is at ('' if it has never been migrated)."""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision() or ""


def prepare_database(engine: Engine) -> None:
    """Create or upgrade the schema so it matches the code. Safe to call repeatedly."""
    postgres = engine.dialect.name == "postgresql"
    with engine.connect() as conn:
        if postgres:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
        try:
            if MigrationContext.configure(conn).get_current_revision() != head_revision():
                command.upgrade(alembic_config(conn), "head")
            conn.commit()
        finally:
            if postgres:
                conn.rollback()                      # leave no failed transaction behind
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY})
                conn.commit()


def main() -> None:
    """`python -m perfagent.db.migrate` — apply migrations to DATABASE_URL and report."""
    from perfagent.config import get_settings
    from perfagent.db.connection import build_engine, safe_url

    url = get_settings().database_url
    engine = build_engine(url)
    before = current_revision(engine)
    prepare_database(engine)
    after = current_revision(engine)
    print(f"database: {safe_url(url)}")
    print(f"revision: {before or '(none)'} -> {after}" if before != after
          else f"revision: {after} (already up to date)")
    engine.dispose()


if __name__ == "__main__":
    main()

__all__ = ["prepare_database", "current_revision", "head_revision", "alembic_config"]
