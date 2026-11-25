"""Evaluate release budgets against an approved, comparable full run."""

from decimal import Decimal
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReleaseBudgets(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    max_p95_ms: float | None = Field(default=None, gt=0, le=3_600_000)
    max_error_percent: float | None = Field(default=None, ge=0, le=100)
    min_rps: float | None = Field(default=None, gt=0, le=1_000_000)
    max_p95_regression_percent: float | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def require_budget(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("Add at least one release budget.")
        return self


def environment(report: dict) -> str:
    return (report.get("execution", {}).get("environment") or "").strip().lower()


def _measurement(value):
    return value if type(value) in (int, float) and isfinite(value) and value >= 0 else None


def measurements(report: dict) -> dict:
    snapshot = report.get("snapshot") or {}
    latency = snapshot.get("latency") or {}
    if not snapshot.get("requests"):
        return {}
    error = _measurement(snapshot.get("error_rate"))
    return {
        "p95_ms": _measurement(latency.get("p95_ms")) if latency.get("samples") != 0 else None,
        "error_percent": float(Decimal(str(error)) * 100) if error is not None else None,
        "rps": _measurement(snapshot.get("rps")),
    }


def full_measurement(report: dict) -> bool:
    execution = report.get("execution") or {}
    return bool(
        report.get("status") == "finished"
        and execution.get("mode", "full") == "full"
        and execution.get("workload_version")
        and any(value is not None for value in measurements(report).values())
    )


def compatible(candidate: dict, baseline: dict) -> bool:
    return (
        full_measurement(candidate)
        and full_measurement(baseline)
        and candidate.get("target") == baseline.get("target")
        and candidate.get("tool", "k6") == baseline.get("tool", "k6")
        and environment(candidate) == environment(baseline)
        and candidate["execution"]["workload_version"] == baseline["execution"]["workload_version"]
    )


def evaluate_release(
    candidate: dict, baseline: dict, budgets: ReleaseBudgets, *, comparable: bool
) -> dict:
    observed = measurements(candidate)
    reference = measurements(baseline) if comparable else {}
    rules = []

    def check(name, actual, limit, op, unit):
        if limit is None:
            return
        if actual is None:
            passed = None
        elif op == "≤":
            passed = actual <= limit
        else:
            passed = actual >= limit
        rules.append(
            {
                "name": name,
                "actual": actual,
                "limit": limit,
                "op": op,
                "unit": unit,
                "passed": passed,
            }
        )

    if full_measurement(candidate):
        check("p95 latency", observed.get("p95_ms"), budgets.max_p95_ms, "≤", "ms")
        check(
            "Request error rate", observed.get("error_percent"), budgets.max_error_percent, "≤", "%"
        )
        check("Request throughput", observed.get("rps"), budgets.min_rps, "≥", "req/s")
        before, after = reference.get("p95_ms"), observed.get("p95_ms")
        delta = None
        if before and after is not None:
            reference_p95 = Decimal(str(before))
            delta = float((Decimal(str(after)) - reference_p95) / reference_p95 * 100)
        check("p95 change from baseline", delta, budgets.max_p95_regression_percent, "≤", "%")

    threshold = candidate.get("verdict", {}).get("overall_passed")
    failed = next((rule for rule in rules if rule["passed"] is False), None)
    if not full_measurement(candidate):
        status, reason = (
            "needs_evidence",
            "A completed full run with request measurements is required.",
        )
    elif failed:
        status, reason = "blocked", failed["name"] + " breached its release budget."
    elif threshold is False:
        status, reason = "blocked", "The candidate breached a k6 threshold."
    elif not comparable:
        status, reason = (
            "needs_evidence",
            "An earlier approved run with the same target and workload is required.",
        )
    elif candidate.get("snapshot", {}).get("dropped_iterations", 0):
        status, reason = (
            "needs_evidence",
            "k6 dropped iterations. Confirm the intended load with another run.",
        )
    elif threshold is None and candidate.get("verdict", {}).get("checks"):
        status, reason = "needs_evidence", "A k6 threshold could not be evaluated."
    elif any(rule["passed"] is None for rule in rules):
        status, reason = "needs_evidence", "A metric required by the release budget is unavailable."
    else:
        status, reason = (
            "ready",
            "All configured release budgets passed under a comparable workload.",
        )

    execution = candidate.get("execution") or {}
    target = execution.get("target_request_rate") if not execution.get("script_edited") else None
    return {
        "status": status,
        "reason": reason,
        "rules": rules,
        "candidate_rps": observed.get("rps"),
        "target_rps": target,
    }
