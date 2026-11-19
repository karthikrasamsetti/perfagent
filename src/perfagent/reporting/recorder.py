"""Persist a RunRecord when a run finishes.

Deterministic; called from the same place analyzer/verdict.py issues the
final verdict. The `summary` argument is the dict already produced by
stats/aggregator.py, so no metric math is duplicated here.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from perfagent.db.models import RunRecord, RunStatus
from perfagent.audit import record_event  # existing audit ledger

log = structlog.get_logger("perfagent.reporting.recorder")

_VERDICT_TO_STATUS = {
    "PASS": RunStatus.PASSED,
    "FAIL": RunStatus.FAILED,
    "INCONCLUSIVE": RunStatus.INCONCLUSIVE,
}


def record_run(
    session: Session, *,
    run_id: str, scenario: str, environment: str, target_url: str,
    load_tool: str, started_at: datetime, verdict: str,
    summary: dict, thresholds: list | None = None,
    coverage: dict | None = None, ai_narrative: str | None = None,
    requested_by: str | None = None,
) -> RunRecord:
    """Insert one historical record. `summary` is the aggregator output."""
    rec = RunRecord(
        run_id=run_id, scenario=scenario,
        environment=environment or "unspecified",
        target_url=target_url, load_tool=load_tool,
        status=_VERDICT_TO_STATUS.get(verdict, RunStatus.INCONCLUSIVE),
        started_at=started_at, finished_at=datetime.now(timezone.utc),
        total_requests=summary.get("total_requests", 0),
        error_rate=summary.get("error_rate", 0.0),
        p50_ms=summary.get("p50"), p90_ms=summary.get("p90"),
        p95_ms=summary.get("p95"), p99_ms=summary.get("p99"),
        rps=summary.get("rps"), max_vus=summary.get("max_vus"),
        verdict=verdict, thresholds=thresholds, coverage=coverage,
        ai_narrative=ai_narrative, requested_by=requested_by,
    )
    session.add(rec)
    session.commit()
    record_event("run_recorded", {"run_id": run_id, "verdict": verdict})
    log.info("run_record_persisted", run_id=run_id, verdict=verdict)
    return rec
