"""Checkpoint local runs for reporting after loss of their in-memory owner."""

import json
import time
from dataclasses import dataclass

from sqlalchemy import select, update

from perfagent.db import get_session
from perfagent.db.models import PlanRow, RunCheckpointRow, ScriptRow
from perfagent.logging_config import get_logger
from perfagent.runner.k6_runner import RunState

OWNER_LEASE_SECONDS = 30
_log = get_logger(__name__)


@dataclass
class RunCheckpoint:
    run: RunState
    owner_expired: bool


def record_launch(run_id: str, script_id: str, target: str, metadata: dict) -> None:
    payload = {
        "target": target, "metadata": metadata, "started_at": time.time(),
    }
    with get_session() as session:
        session.add(RunCheckpointRow(
            run_id=run_id, script_id=script_id, updated_at=time.time(), payload_json=json.dumps(payload),
        ))
        session.commit()


def discard_launch(run_id: str) -> None:
    with get_session() as session:
        row = session.get(RunCheckpointRow, run_id)
        if row is not None:
            session.delete(row)
            session.commit()


def checkpoint_run(run: RunState) -> None:
    payload = {
        "target": run.target, "metadata": run.metadata, "started_at": run.started_at,
        "run_start_ts": run.run_start_ts, "snapshot": run.snapshot,
        "samples": run.samples[-1200:], "logs": run.logs[-200:],
    }
    try:
        with get_session() as session:
            session.execute(update(RunCheckpointRow).where(RunCheckpointRow.run_id == run.run_id)
                            .values(updated_at=time.time(), payload_json=json.dumps(payload)))
            session.commit()
    except Exception as error:
        _log.warning("run.checkpoint_failed", run_id=run.run_id, error_type=type(error).__name__)


def saved_checkpoint(run_id: str) -> RunCheckpoint | None:
    with get_session() as session:
        row = session.get(RunCheckpointRow, run_id)
        if row is None:
            return None
        payload = json.loads(row.payload_json)
        expired = time.time() - row.updated_at >= OWNER_LEASE_SECONDS
        run = RunState(
            run_id=run_id, script_id=row.script_id, tool="k6", target=payload["target"],
            status="stopped" if expired else "preparing", started_at=payload["started_at"],
            ended_at=row.updated_at if expired else None,
            message=("Run interrupted. The execution process stopped updating its checkpoint."
                     if expired else "Waiting for the runner’s saved checkpoint."),
            snapshot=payload.get("snapshot", {}), samples=payload.get("samples", []),
            logs=payload.get("logs", []), metadata=payload["metadata"],
            run_start_ts=payload.get("run_start_ts"),
        )
    return RunCheckpoint(run=run, owner_expired=expired)


def expired_project_runs(project_id: str, limit: int) -> list[str]:
    with get_session() as session:
        return list(session.scalars(
            select(RunCheckpointRow.run_id)
            .join(ScriptRow, ScriptRow.id == RunCheckpointRow.script_id)
            .join(PlanRow, PlanRow.id == ScriptRow.plan_id)
            .where(PlanRow.project_id == project_id,
                   RunCheckpointRow.updated_at <= time.time() - OWNER_LEASE_SECONDS)
            .order_by(RunCheckpointRow.updated_at, RunCheckpointRow.run_id)
            .limit(limit)
        ))
