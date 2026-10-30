"""Database — persists plans, scripts, and uploaded data files, with lineage.

Phase 3 uses SQLite by default (a file on disk) so there's nothing to install.
Swapping to Postgres later is a one-line URL change. Each script row points back to
the plan row it came from; a data-file row is standalone (uploaded once, referenced
by filename in the plan's LoadModel) so lineage is queryable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
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


_engine = None


def get_engine(db_url: str = "sqlite:///perfagent.db"):
    global _engine
    if _engine is None:
        _engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    return Session(get_engine())