"""Reporting endpoints — role-scoped history and a p95 trend, read from the
existing RunResultRow table (the one every finished run already writes to).

No separate run_records table, no new write step: these endpoints read the
runs your app already records, so they return real data immediately.

  /api/reporting/runs   -> run history, fields limited per stakeholder role
  /api/reporting/trend  -> p95 (or error rate / rps) across recent runs

Deterministic; reads stored data only. Uses the same `with get_session() as s:`
pattern as the rest of the app, and registers each route in api/docs.py via
**doc(...), so tests/test_api_docs.py stays green.
"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Query, HTTPException

from perfagent.db import RunResultRow, PlanRow, get_session
from perfagent.api.docs import doc
from perfagent.api.test_identity import saved_identity

router = APIRouter()


class Role(str, Enum):
    EXECUTIVE = "executive"   # headline verdict + key latency only
    QA_LEAD = "qa_lead"       # full metrics
    ENGINEER = "engineer"     # everything, incl. goal + plan linkage
    VIEWER = "viewer"         # minimal summary


# What each role is allowed to see. A whitelist, so adding a column never
# leaks to a lower role by accident. ENGINEER (empty set) sees everything.
_ROLE_FIELDS: dict[Role, set[str]] = {
    Role.EXECUTIVE: {"run_id", "created_at", "target", "verdict",
                     "p95_ms", "error_rate", "requests", "mode", "test_name", "script_name", "endpoint_summary"},
    Role.QA_LEAD: {"run_id", "created_at", "target", "goal", "verdict",
                   "requests", "error_rate", "p95_ms", "p99_ms", "avg_ms",
                   "rps", "mode", "test_name", "script_name", "endpoint_summary"},
    Role.ENGINEER: set(),     # empty => all fields
    Role.VIEWER: {"run_id", "created_at", "verdict", "p95_ms", "requests", "mode", "test_name", "script_name"},
}


def _full(r: RunResultRow, session=None) -> dict:
    """Every reportable field of a run result row."""
    report = json.loads(r.report_json or "{}")
    execution = report.get("execution", {})
    return {
        **saved_identity(r, session),
        "run_id": r.id,
        "plan_id": r.plan_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "target": r.target_base_url,
        "goal": r.goal,
        "verdict": r.verdict,
        "requests": r.requests,
        "error_rate": r.error_rate,
        "p95_ms": r.p95_ms,
        "p99_ms": r.p99_ms,
        "avg_ms": r.avg_ms,
        "rps": r.rps,
        "has_report": bool(r.report_json),
        "environment": execution.get("environment", ""),
        "release_label": execution.get("release_label", ""),
        "mode": execution.get("mode", "full"),
        "workload_version": execution.get("workload_version"),
    }


def _project(r: RunResultRow, role: Role, session=None) -> dict:
    full = _full(r, session)
    allowed = _ROLE_FIELDS[role]
    return full if not allowed else {k: full[k] for k in allowed if k in full}


@router.get("/api/reporting/runs", **doc("GET", "/api/reporting/runs"))
def reporting_runs(
    role: Role = Query(Role.VIEWER),
    target: str | None = Query(None, description="Filter by target base URL"),
    verdict: str | None = Query(None, description="pass | fail | inconclusive"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    plan_id: str | None = Query(None),
    project_id: str | None = Query(None),
) -> dict:
    """Run history, newest first, with each run's fields limited to the role."""
    if since and since.tzinfo:
        since = since.astimezone(timezone.utc).replace(tzinfo=None)
    if until and until.tzinfo:
        until = until.astimezone(timezone.utc).replace(tzinfo=None)
    if since and until and since > until:
        raise HTTPException(400, "From date must precede the through date.")
    if role == Role.VIEWER and target:
        raise HTTPException(400, "Target filtering is unavailable for the Viewer role.")
    with get_session() as s:
        q = s.query(RunResultRow)
        if project_id:
            q = q.join(PlanRow, PlanRow.id == RunResultRow.plan_id).filter(PlanRow.project_id == project_id)
        if plan_id:
            q = q.filter(RunResultRow.plan_id == plan_id)
        if target:
            q = q.filter(RunResultRow.target_base_url.contains(target, autoescape=True))
        if verdict:
            q = q.filter(RunResultRow.verdict == verdict)
        if since:
            q = q.filter(RunResultRow.created_at >= since)
        if until:
            q = q.filter(RunResultRow.created_at < until)
        total = q.count()
        rows = (q.order_by(RunResultRow.created_at.desc(), RunResultRow.id.desc())
                 .offset(offset).limit(limit).all())
        return {"role": role.value, "count": len(rows),
                "total": total, "offset": offset, "limit": limit,
                "runs": [_project(r, role, s) for r in rows]}


@router.get("/api/reporting/trend", **doc("GET", "/api/reporting/trend"))
def reporting_trend(
    metric: str = Query("p95_ms", pattern="^(p95_ms|p99_ms|error_rate|rps|avg_ms)$"),
    target: str | None = Query(None, description="Filter by target base URL"),
    plan_id: str | None = Query(None, description="Filter by plan"),
    limit: int = Query(30, ge=1, le=365),
) -> dict:
    """One metric across recent runs, oldest->newest, for a trend chart."""
    with get_session() as s:
        q = s.query(RunResultRow)
        if target:
            q = q.filter(RunResultRow.target_base_url == target)
        if plan_id:
            q = q.filter(RunResultRow.plan_id == plan_id)
        rows = (q.order_by(RunResultRow.created_at.desc())
                 .limit(limit).all())
        rows = list(reversed(rows))   # oldest first for a left-to-right chart
        points = []
        for r in rows:
            value = getattr(r, metric, None)
            if value is not None:
                points.append({
                    "t": r.created_at.isoformat() if r.created_at else None,
                    "value": value,
                    "verdict": r.verdict,
                })
        return {"metric": metric, "target": target, "plan_id": plan_id,
                "points": points}
