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
from hashlib import sha256
from math import isfinite

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import JSON, case, cast, func

from perfagent.db import RunResultRow, PlanRow, get_session
from perfagent.api.docs import doc
from perfagent.api.test_identity import saved_identity
from perfagent.analyzer.baseline import compare

router = APIRouter()


class Role(str, Enum):
    EXECUTIVE = "executive"   # headline verdict + key latency only
    QA_LEAD = "qa_lead"       # full metrics
    ENGINEER = "engineer"     # everything, incl. goal + plan linkage
    VIEWER = "viewer"         # minimal summary


# What each role is allowed to see. A whitelist, so adding a column never
# leaks to a lower role by accident. ENGINEER (empty set) sees everything.
_ROLE_FIELDS: dict[Role, set[str]] = {
    Role.EXECUTIVE: {"has_report", "run_id", "created_at", "target", "verdict",
                     "p50_ms", "p95_ms", "error_rate", "requests", "rps", "mode", "test_name", "script_name", "endpoint_summary",
                     "environment", "release_label", "workload_version"},
    Role.QA_LEAD: {"has_report", "run_id", "created_at", "target", "goal", "verdict",
                   "requests", "error_rate", "p50_ms", "p95_ms", "p99_ms", "avg_ms",
                   "rps", "mode", "test_name", "script_name", "endpoint_summary",
                   "environment", "release_label", "workload_version"},
    Role.ENGINEER: set(),     # empty => all fields
    Role.VIEWER: {"has_report", "run_id", "created_at", "verdict", "p95_ms", "requests", "mode", "test_name", "script_name"},
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
        "p50_ms": (report.get("snapshot", {}).get("latency") or {}).get("p50_ms"),
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


_DASHBOARD_TREND_LIMIT = 120


def _observed_metrics(report: dict, role: Role) -> dict:
    snapshot = report.get("snapshot") or {}
    if not snapshot.get("requests"):
        return {}
    latency = snapshot.get("latency") or {}
    measured = {key: snapshot.get(key) for key in ("error_rate", "rps")}
    if latency.get("samples") != 0:
        measured.update({key: latency.get(key) for key in ("avg_ms", "p95_ms", "p99_ms")})
    allowed = _ROLE_FIELDS[role]
    return {key: value for key, value in measured.items()
            if (not allowed or key in allowed)
            and type(value) in (int, float) and isfinite(value) and value >= 0}


def _latest_regression(latest: RunResultRow | None, role: Role, session) -> dict | None:
    if latest is None:
        return None
    report = json.loads(latest.report_json or "{}")
    execution = report.get("execution") or {}
    if (report.get("status") != "finished" or not report.get("baseline_id")
            or not execution.get("workload_version")):
        return None
    baseline = session.get(RunResultRow, report["baseline_id"])
    if (baseline is None or baseline.plan_id != latest.plan_id
            or baseline.target_base_url != latest.target_base_url
            or not baseline.created_at or not latest.created_at
            or baseline.created_at >= latest.created_at):
        return None
    earlier = json.loads(baseline.report_json or "{}")
    earlier_execution = earlier.get("execution") or {}
    if earlier.get("status") != "finished" or any(
        (execution.get(key) or default) != (earlier_execution.get(key) or default)
        for key, default in (("workload_version", None), ("mode", "full"), ("environment", ""))
    ):
        return None
    comparison = compare(_observed_metrics(report, role), _observed_metrics(earlier, role))
    changes = [
        {"label": delta["label"], "metric": delta["metric"],
         "previous_fmt": delta["previous_fmt"], "current_fmt": delta["current_fmt"]}
        for delta in comparison["deltas"] if delta["direction"] == "worse"
    ]
    if not changes:
        return None
    return {"run": _project(latest, role, session), "baseline_id": baseline.id, "changes": changes}


def _overview(query, role: Role, session) -> dict:
    counts = query.with_entities(
        func.count(RunResultRow.id),
        func.sum(case((RunResultRow.verdict == "pass", 1), else_=0)),
        func.sum(case((RunResultRow.verdict == "fail", 1), else_=0)),
        func.sum(RunResultRow.requests),
        func.max(case((RunResultRow.requests > 0, RunResultRow.p95_ms))),
    ).one()
    total, passed, failed, requests, worst_p95 = counts
    latest = (query.order_by(RunResultRow.created_at.desc(), RunResultRow.id.desc()).first()
              if total else None)
    attention = (query.filter(RunResultRow.verdict == "fail")
                 .order_by(RunResultRow.created_at.desc(), RunResultRow.id.desc()).first()
                 if failed else None)
    trend_query = query.with_entities(
        RunResultRow.id, RunResultRow.created_at, RunResultRow.requests, RunResultRow.p95_ms,
        RunResultRow.report_json, RunResultRow.plan_id, RunResultRow.target_base_url, RunResultRow.verdict,
    )
    recent = trend_query.order_by(
        RunResultRow.created_at.desc(), RunResultRow.id.desc()
    ).limit(_DASHBOARD_TREND_LIMIT).all()
    trend = []
    for row in reversed(recent):
        report = json.loads(row.report_json or "{}")
        execution = report.get("execution") or {}
        measured = _observed_metrics(report, role)
        snapshot = report.get("snapshot") or {}
        latency = snapshot.get("latency") or {}
        version = execution.get("workload_version")
        p95_limit = next((rule.get("target") for rule in (report.get("verdict") or {}).get("checks", [])
                          if rule.get("metric") == "p95_ms" and rule.get("op") in ("<", "<=")), None)
        group = [row.plan_id, row.target_base_url, execution.get("environment"),
                 execution.get("mode", "full"), version] if version else [row.id]
        trend.append({
            "t": row.created_at.isoformat() if row.created_at else None,
            "run_id": row.id, "verdict": row.verdict, "has_report": bool(row.report_json),
            "test_name": execution.get("test_name"),
            "series_group": sha256(json.dumps(group).encode()).hexdigest(),
            "p95_ms": measured.get("p95_ms") if report else row.p95_ms if row.requests else None,
            "p95_limit": p95_limit,
            **({"p50_ms": latency.get("p50_ms") if snapshot.get("requests") and latency.get("samples") != 0 else None,
                "p99_ms": measured.get("p99_ms"), "error_rate": measured.get("error_rate"),
                "rps": measured.get("rps"),
                "target_rps": execution.get("target_request_rate") if not execution.get("script_edited") else None}
               if role != Role.VIEWER else {}),
        })
    day = func.date(RunResultRow.created_at)
    outcomes = query.with_entities(
        day.label("day"), func.count(RunResultRow.id).label("total"),
        func.sum(case((RunResultRow.verdict == "pass", 1), else_=0)).label("passed"),
        func.sum(case((RunResultRow.verdict == "fail", 1), else_=0)).label("failed"),
    ).group_by(day).order_by(day.desc()).limit(_DASHBOARD_TREND_LIMIT).all()
    return {
        "total": total,
        "passed": passed or 0,
        "failed": failed or 0,
        "inconclusive": total - (passed or 0) - (failed or 0),
        "requests": requests or 0,
        "worst_p95_ms": worst_p95,
        "latest": _project(latest, role, session) if latest else None,
        "attention": _project(attention, role, session) if attention else None,
        "regression": _latest_regression(latest, role, session),
        "trend": trend,
        "outcomes": [{"day": str(item.day), "pass": item.passed, "fail": item.failed,
                      "inconclusive": item.total - item.passed - item.failed} for item in reversed(outcomes)],
    }


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
    environment: str | None = Query(None, max_length=120),
    release_label: str | None = Query(None, max_length=120),
    include_overview: bool = Query(False),
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
    if role == Role.VIEWER and (environment or release_label):
        raise HTTPException(400, "Environment and release filtering are unavailable for the Viewer role.")
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
        for key, value in (("environment", environment), ("release_label", release_label)):
            if value:
                document = func.nullif(RunResultRow.report_json, "")
                field = (func.json_extract(document, f"$.execution.{key}")
                         if s.bind.dialect.name == "sqlite"
                         else cast(document, JSON)["execution"][key].as_string())
                q = q.filter(func.lower(field) == value.lower())
        if since:
            q = q.filter(RunResultRow.created_at >= since)
        if until:
            q = q.filter(RunResultRow.created_at < until)
        overview = _overview(q, role, s) if include_overview else None
        total = overview["total"] if overview is not None else q.count()
        rows = (q.order_by(RunResultRow.created_at.desc(), RunResultRow.id.desc())
                 .offset(offset).limit(limit).all())
        return {"role": role.value, "count": len(rows),
                "total": total, "offset": offset, "limit": limit,
                "runs": [_project(r, role, s) for r in rows],
                **({"overview": overview} if overview is not None else {})}


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
