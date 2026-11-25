"""Manage release policy using saved runs inside the workspace access boundary."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from perfagent.analyzer.release import (
    ReleaseBudgets,
    compatible,
    environment,
    evaluate_release,
    full_measurement,
    measurements,
)
from perfagent.api.docs import doc
from perfagent.db import AuditRow, PlanRow, RunResultRow, get_session
from perfagent.db.models import ReleasePolicyRow

router = APIRouter()
_POLICY_PATH = "/api/runs/{run_id}/release-policy"


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budgets: ReleaseBudgets


def release_readiness(
    session, row: RunResultRow, report: dict, *, comparison_details=False
) -> dict:
    scope = environment(report)
    policy = session.get(ReleasePolicyRow, (row.plan_id, scope))
    if policy is None:
        return {
            "status": "needs_evidence",
            "reason": "Approve a baseline and set release budgets for this environment.",
            "environment": scope,
        }
    baseline = session.get(RunResultRow, policy.baseline_id)
    reference = (
        json.loads(baseline.report_json or "{}")
        if baseline and baseline.plan_id == row.plan_id
        else {}
    )
    comparable = bool(
        reference
        and baseline.created_at < row.created_at
        and baseline.target_base_url == row.target_base_url
        and compatible(report, reference)
    )
    budgets = ReleaseBudgets.model_validate_json(policy.budgets_json)
    result = evaluate_release(report, reference, budgets, comparable=comparable)
    if row.id == policy.baseline_id:
        result.update(
            status="needs_evidence",
            reason="This run is the approved baseline. Run a new candidate for a decision.",
        )
    result.update(
        environment=scope,
        baseline_id=policy.baseline_id,
        candidate_id=row.id,
        approved_at=policy.approved_at.isoformat() + "Z",
        budgets=budgets.model_dump(),
        baseline_release=(reference.get("execution") or {}).get("release_label"),
        candidate_release=(report.get("execution") or {}).get("release_label"),
    )
    if comparable:
        before = measurements(reference).get("p95_ms")
        current = measurements(report).get("p95_ms")
        if before is not None and current is not None:
            result["summary"] = (
                f"p95 latency was {current:.6g} ms. The approved baseline was {before:.6g} ms."
            )
            result["p95_comparison"] = {"baseline_ms": before, "candidate_ms": current}
        changes = endpoint_changes(report, reference)
        if changes and changes[0]["candidate_ms"] > changes[0]["baseline_ms"]:
            result["largest_endpoint_increase"] = changes[0]
        if comparison_details:
            result["comparison"] = comparison_evidence(report, reference, changes=changes)
    verdict = (report.get("verdict") or {}).get("overall_passed")
    threshold_summary = {
        True: "The run passed its k6 thresholds.",
        False: "The run breached a k6 threshold.",
        None: "The run has no conclusive k6 threshold verdict.",
    }[verdict]
    if result["status"] == "blocked":
        outcome = "The release is blocked. " + result["reason"]
    elif result["status"] == "ready":
        outcome = "The release is ready. All configured release budgets were met."
    else:
        outcome = "The release decision needs more evidence. " + result["reason"]
    result["explanation"] = f"{threshold_summary} {outcome}"
    return result


def endpoint_changes(report: dict, reference: dict) -> list[dict]:
    def endpoints(payload):
        return {
            item["name"]: item
            for item in (payload.get("snapshot") or {}).get("per_endpoint", [])
            if item.get("name") and item.get("p95_ms") is not None and item.get("requests")
        }

    current, before = endpoints(report), endpoints(reference)
    changes = [
        {"name": name, "candidate_ms": value["p95_ms"], "baseline_ms": before[name]["p95_ms"]}
        for name, value in current.items()
        if name in before
    ]
    changes.sort(key=lambda item: item["candidate_ms"] - item["baseline_ms"], reverse=True)
    return changes


def comparison_evidence(report: dict, reference: dict, *, changes: list[dict]) -> dict:
    def series(payload):
        samples = payload.get("samples") or []
        stride = max(1, (len(samples) + 239) // 240)
        return [
            {key: point.get(key) for key in ("t", "rps", "p95", "err", "dropped_iterations")}
            for point in samples[::stride]
        ]

    return {
        "baseline": series(reference),
        "candidate": series(report),
        "endpoints": changes[:20],
        "baseline_metrics": measurements(reference),
        "candidate_metrics": measurements(report),
        "phases": report["execution"].get("planned_phases") or [],
    }


@router.put(_POLICY_PATH, **doc("PUT", _POLICY_PATH))
def approve_release_policy(run_id: str, body: PolicyInput, request: Request) -> dict:
    """Use the saved run as the reference for its own test and environment."""
    with get_session() as session:
        row = session.get(RunResultRow, run_id)
        if row is None or not row.report_json or session.get(PlanRow, row.plan_id) is None:
            raise HTTPException(404, "Saved test run not found.")
        report = json.loads(row.report_json)
        if (
            not full_measurement(report)
            or row.verdict != "pass"
            or (report.get("snapshot") or {}).get("dropped_iterations")
        ):
            raise HTTPException(
                422,
                "Choose a completed full run with passing thresholds and no dropped iterations.",
            )
        if body.budgets.max_p95_regression_percent is not None and not measurements(report).get(
            "p95_ms"
        ):
            raise HTTPException(
                422, "The baseline needs a measured p95 above zero for a percentage comparison."
            )

        if len(environment(report)) > 120:
            raise HTTPException(422, "Use an environment label of 120 characters or fewer.")
        values = {
            "plan_id": row.plan_id,
            "environment": environment(report),
            "baseline_id": row.id,
            "budgets_json": body.budgets.model_dump_json(),
            "approved_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
        statement = insert(ReleasePolicyRow).values(**values)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["plan_id", "environment"],
                set_={
                    key: statement.excluded[key]
                    for key in ("baseline_id", "budgets_json", "approved_at")
                },
            )
        )
        principal = getattr(request.state, "principal", None)
        session.add(
            AuditRow(
                action="release.baseline_approved",
                entity="run",
                entity_id=row.id,
                actor=principal.subject if principal else "local",
                summary="Approved a saved run and updated release budgets.",
            )
        )
        session.commit()
        return release_readiness(session, row, report)
