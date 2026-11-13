"""Database connection — one URL decides SQLite or Postgres.

    DATABASE_URL=sqlite:///perfagent.db                         (default: a local file)
    DATABASE_URL=postgresql://user:password@host:5432/perfagent  (shared, for hosting)

Everything else in the app talks to the database through SQLAlchemy's ORM, so the
same code runs on both. The differences Postgres brings are handled here, once:

  - Driver      `postgresql://` and `postgres://` URLs are routed to psycopg 3.
  - Time zone   timestamp columns hold naive UTC. The Postgres session is pinned to
                UTC so values are stored and read back exactly as on SQLite, whatever
                the server's own time zone is.
  - Lengths     Postgres enforces VARCHAR(n) and SQLite does not. Text written to a
                sized column is trimmed to fit instead of failing the request.
  - NUL bytes   Postgres text cannot hold \\x00; they are removed on write.
  - Pooling     connections are pooled and checked before use (pre-ping), so a
                database restart doesn't leave the app holding dead connections.
"""

from __future__ import annotations

from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Mapper

DEFAULT_SQLITE_URL = "sqlite:///perfagent.db"

_PG_DRIVER = "postgresql+psycopg"


def normalise_url(url: str | None) -> URL:
    """Parse a database URL, sending any Postgres spelling to the psycopg 3 driver."""
    parsed = make_url((url or "").strip() or DEFAULT_SQLITE_URL)
    backend = parsed.get_backend_name()            # 'postgresql' | 'sqlite' | ...
    if backend in ("postgresql", "postgres"):
        parsed = parsed.set(drivername=_PG_DRIVER)
    return parsed


def is_postgres(url: str | URL | None) -> bool:
    parsed = normalise_url(url) if not isinstance(url, URL) else url
    return parsed.get_backend_name() == "postgresql"


def safe_url(url: str | URL | None) -> str:
    """The URL with the password hidden — the only form that may be logged or shown."""
    parsed = normalise_url(url) if not isinstance(url, URL) else url
    return parsed.render_as_string(hide_password=True)


def libpq_url(url: str | URL | None) -> str:
    """The plain `postgresql://…` form (no SQLAlchemy driver suffix), for libraries
    that connect with psycopg directly (the LangGraph checkpoint store)."""
    parsed = normalise_url(url) if not isinstance(url, URL) else url
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)


def build_engine(url: str | None, *, pool_size: int = 5) -> Engine:
    """Create the engine for a database URL (no tables are created here)."""
    parsed = normalise_url(url)
    if parsed.get_backend_name() == "postgresql":
        return create_engine(
            parsed,
            echo=False,
            pool_pre_ping=True,                 # survive a database restart
            pool_size=pool_size,
            max_overflow=pool_size,
            pool_recycle=1800,
            # Timestamps are naive UTC in every table; pin the session so Postgres
            # never shifts them to the server's local time.
            connect_args={"options": "-c timezone=utc", "connect_timeout": 10},
        )
    return create_engine(parsed, echo=False)


# ---------- write-time sanitising (applies to every table) ----------

def _sanitise(mapper: Mapper, _connection, target) -> None:
    """Make string values safe for Postgres before they are written."""
    for column in mapper.columns:
        if not isinstance(column.type, String):
            continue                              # String covers Text too
        key = mapper.get_property_by_column(column).key
        value = getattr(target, key, None)
        if not isinstance(value, str):
            continue
        cleaned = value.replace("\x00", "") if "\x00" in value else value
        limit = column.type.length
        if limit and len(cleaned) > limit:
            cleaned = cleaned[:limit]
        if cleaned is not value:
            setattr(target, key, cleaned)


def install_sanitiser(base) -> None:
    """Attach the sanitiser to every model derived from ``base``."""
    event.listen(base, "before_insert", _sanitise, propagate=True)
    event.listen(base, "before_update", _sanitise, propagate=True)


__all__ = ["DEFAULT_SQLITE_URL", "normalise_url", "is_postgres", "safe_url", "libpq_url",
           "build_engine", "install_sanitiser"]
