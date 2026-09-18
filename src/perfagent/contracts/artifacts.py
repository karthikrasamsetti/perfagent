"""Artifacts — the persisted outputs of each stage, connected by lineage.

In Phase 1 these are plain in-memory objects. When we add the database (later
session), these map to SQLAlchemy rows; the shape stays the same. Each artifact
carries a pointer to its parent so a downstream artifact always traces back to
what produced it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from perfagent.contracts.load_model import LoadModel


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlanArtifact(BaseModel):
    """Output of the Plan stage: a LoadModel with an identity."""

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    load_model: LoadModel


class ScriptArtifact(BaseModel):
    """Output of the Generate stage: a rendered script for one tool.

    `plan_id` is the lineage link back to the PlanArtifact it was generated from.
    """

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    plan_id: str
    tool: str
    filename: str
    content: str
