"""Role-scoped projection of run records.

A whitelist per role, so new sensitive columns never leak by default.
Empty set means full access. Maps onto the x-access classification:
executive/viewer are read-level consumers, engineer sees internals
including the AI narrative.
"""
from __future__ import annotations

from enum import Enum

from perfagent.db.models import RunRecord


class Role(str, Enum):
    EXECUTIVE = "executive"   # headline verdict + trend only
    QA_LEAD = "qa_lead"       # full metrics + coverage + thresholds
    ENGINEER = "engineer"     # everything, incl. target_url + narrative
    VIEWER = "viewer"         # minimal read-only summary


_ROLE_FIELDS: dict[Role, set[str]] = {
    Role.EXECUTIVE: {"run_id", "scenario", "environment", "status",
                     "started_at", "verdict", "p95_ms", "error_rate"},
    Role.QA_LEAD: {"run_id", "scenario", "environment", "target_url",
                   "status", "started_at", "finished_at", "verdict",
                   "p50_ms", "p90_ms", "p95_ms", "p99_ms", "error_rate",
                   "rps", "max_vus", "total_requests", "thresholds",
                   "coverage"},
    Role.ENGINEER: set(),     # empty => all columns
    Role.VIEWER: {"run_id", "scenario", "status", "verdict", "p95_ms"},
}


def project(record: RunRecord, role: Role) -> dict:
    """Return only the fields `role` is permitted to see."""
    full = record.as_full_dict()
    allowed = _ROLE_FIELDS[role]
    return full if not allowed else {k: full[k] for k in allowed if k in full}
