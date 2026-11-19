"""Database — persists plans, scripts, and uploaded data files, with lineage.

SQLite by default (a file on disk) so there's nothing to install; Postgres when
DATABASE_URL points at one (see db/connection.py). The models below are the same
for both. Schema changes go through Alembic migrations (db/migrate.py).

Each script row points back to
the plan row it came from; a data-file row is standalone (uploaded once, referenced
by filename in the plan's LoadModel) so lineage is queryable.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from perfagent.db.connection import build_engine, install_sanitiser, safe_url
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Enum as SAEnum, JSON, Text,
)

def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")


class WorkloadRow(Base):
    __tablename__ = "test_workloads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    plan_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    profile_json: Mapped[str] = mapped_column(Text)
    thresholds_json: Mapped[str] = mapped_column(Text, default="[]")


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    target_base_url: Mapped[str] = mapped_column(String(500))
    goal: Mapped[str] = mapped_column(Text, default="")
    # The full LoadModel stored as JSON text (model_dump_json).
    load_model_json: Mapped[str] = mapped_column(Text)

    scripts: Mapped[list[ScriptRow]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class ScriptRow(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"))
    tool: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)

    plan: Mapped[PlanRow] = relationship(back_populates="scripts")


class DataFileRow(Base):
    """An uploaded test-data file. Content is stored so the runner can write it
    next to the generated script at run time. Values never go to the LLM."""

    __tablename__ = "data_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    filename: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(20), default="csv")
    columns_csv: Mapped[str] = mapped_column(Text, default="")   # comma-joined field names
    row_count: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text)                    # the raw file text

    @property
    def columns(self) -> list[str]:
        return [c for c in self.columns_csv.split(",") if c]


class ScriptSnapshotRow(Base):
    """Immutable execution inputs for a script version (never sent in reports)."""

    __tablename__ = "script_snapshots"
    script_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    load_model_json: Mapped[str] = mapped_column(Text, default="")
    data_filename: Mapped[str] = mapped_column(Text, default="")
    data_content: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class RunResultRow(Base):
    """A finished run's key metrics — stored so later runs can compare against it
    (baseline / regression). One row per completed run of a plan."""

    __tablename__ = "run_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    plan_id: Mapped[str] = mapped_column(String(32), index=True)
    target_base_url: Mapped[str] = mapped_column(String(500), default="")
    verdict: Mapped[str] = mapped_column(String(20), default="")   # pass/fail/inconclusive/none
    requests: Mapped[int] = mapped_column(default=0)
    error_rate: Mapped[float] = mapped_column(default=0.0)
    rps: Mapped[float] = mapped_column(default=0.0)
    p95_ms: Mapped[float] = mapped_column(default=0.0)
    p99_ms: Mapped[float] = mapped_column(default=0.0)
    avg_ms: Mapped[float] = mapped_column(default=0.0)
    goal: Mapped[str] = mapped_column(Text, default="")        # plan goal, for the history list
    report_json: Mapped[str] = mapped_column(Text, default="")  # full saved report (verdict, diagnosis, narrative...)


class AuditRow(Base):
    """A durable record of a consequential action — who/what/when, for the activity log.

    This is the audit trail: plan created/approved, script generated, run started (with
    target + user count — the action with real consequences), run finished, downloads.
    Never stores secrets or raw bodies — ids, targets, counts and a short summary only.
    """

    __tablename__ = "audit"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)   # e.g. run.started
    entity: Mapped[str] = mapped_column(String(20), default="")   # plan|script|run|data
    entity_id: Mapped[str] = mapped_column(String(32), default="")
    target: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(80), default="local")  # future: real user
    tokens: Mapped[int] = mapped_column(default=0)      # LLM tokens for this action
    cost_usd: Mapped[float] = mapped_column(default=0.0)  # rough cost estimate


class SlaProfileRow(Base):
    """A reusable named set of thresholds (an SLA), applicable to any plan."""

    __tablename__ = "sla_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    name: Mapped[str] = mapped_column(String(120))
    thresholds_json: Mapped[str] = mapped_column(Text, default="[]")


class TraceRow(Base):
    """A trace of a single LLM call — for debugging the AI steps.

    Records which step called the model, the model, token usage, latency, and whether
    it succeeded, so you can see 'the dynamize call took 3.2s / 1,400 tokens / ok'.
    """

    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    step: Mapped[str] = mapped_column(String(40), default="")   # plan | chat | dynamize | narrate
    model: Mapped[str] = mapped_column(String(80), default="")
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | error
    redactions: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class IntegrationSettingsRow(Base):
    """Saved, NON-secret Git and Jenkins details, so users don't retype them.

    One row per plan (plan_id = the plan's id) plus one row with plan_id "__last__"
    holding the most recently used values, used as defaults for new plans.
    Tokens, API keys and test secrets are never stored here (see perfagent.integrations).
    Its own table, so existing databases just gain it on start-up — no migration.
    """

    __tablename__ = "integration_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    plan_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
    git_json: Mapped[str] = mapped_column(Text, default="{}")       # repo, branch, framework, ...
    jenkins_json: Mapped[str] = mapped_column(Text, default="{}")   # url, user name, job, ...


class ChatSessionRow(Base):
    """One planning conversation — the index row for the Conversation mode.

    The conversation itself (messages, the structured draft, the last plan) lives in
    the LangGraph checkpoint store, keyed by this row's id (the thread id). This row
    only holds what the "recent conversations" list needs. Message text is stored
    with one-way secrets already masked. Its own table, so existing databases just
    gain it on start-up — no migration.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    test_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    # collecting | ready | planned
    status: Mapped[str] = mapped_column(String(20), default="collecting")
    turns: Mapped[int] = mapped_column(default=0)                # user turns so far
    plan_id: Mapped[str] = mapped_column(String(32), default="")  # last plan built from it


install_sanitiser(Base)

_engine = None
_engine_lock = threading.Lock()


def get_engine(db_url: str | None = None):
    """The app's database engine, created on first use.

    The URL comes from the DATABASE_URL setting (SQLite file by default, Postgres
    when set). On first use the schema is brought up to date — see db/migrate.py.
    """
    global _engine
    if _engine is None:
        # The page fires several API calls at once on load; the lock makes sure only
        # one of them sets the database up.
        with _engine_lock:
            if _engine is None:
                from perfagent.config import get_settings
                from perfagent.db.migrate import prepare_database
                from perfagent.logging_config import get_logger

                settings = get_settings()
                url = db_url or settings.database_url
                engine = build_engine(url, pool_size=settings.database_pool_size)
                try:
                    prepare_database(engine)
                except Exception as e:
                    engine.dispose()
                    get_logger("perfagent.db").error(
                        "db.unavailable", database=safe_url(url),
                        error=f"{type(e).__name__}: {e}"[:400])
                    raise RuntimeError(
                        f"Could not open the database at {safe_url(url)}. Check "
                        f"DATABASE_URL and that the database is running and reachable. "
                        f"({type(e).__name__})") from e
                get_logger("perfagent.db").info(
                    "db.ready", backend=engine.url.get_backend_name(), database=safe_url(url))
                _engine = engine
    return _engine


def get_session() -> Session:
    return Session(get_engine())

class RunStatus(str, enum.Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class RunRecord(Base):
    __tablename__ = "run_records"

    run_id = Column(String, primary_key=True)
    scenario = Column(String, nullable=False, index=True)
    environment = Column(String, nullable=False, index=True)
    target_url = Column(String, nullable=False)
    load_tool = Column(String, nullable=False, default="k6")
    status = Column(SAEnum(RunStatus), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    total_requests = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    p50_ms = Column(Float, nullable=True)
    p90_ms = Column(Float, nullable=True)
    p95_ms = Column(Float, nullable=True)
    p99_ms = Column(Float, nullable=True)
    rps = Column(Float, nullable=True)
    max_vus = Column(Integer, nullable=True)

    verdict = Column(String, nullable=True)
    thresholds = Column(JSON, nullable=True)
    coverage = Column(JSON, nullable=True)
    ai_narrative = Column(Text, nullable=True)
    requested_by = Column(String, nullable=True)

    def as_full_dict(self) -> dict:
        out = {}
        for c in self.__table__.columns:
            v = getattr(self, c.name)
            if isinstance(v, datetime):
                v = v.isoformat()
            elif isinstance(v, RunStatus):
                v = v.value
            out[c.name] = v
        return out
