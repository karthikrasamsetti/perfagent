"""Deterministic verdict — code decides pass/fail, never the LLM.

Compares a run's actual metrics (from the aggregator snapshot) against the plan's
thresholds and returns a structured verdict. Every number and every pass/fail here
is computed in code. The AI later narrates this verdict but cannot change it.
"""

from __future__ import annotations

from perfagent.contracts.load_model import LoadModel


def _metric_value(snapshot: dict, metric: str) -> float | None:
    lat = snapshot.get("latency", {})
    mapping = {
        "p50_ms": lat.get("p50_ms"),
        "p90_ms": lat.get("p90_ms"),
        "p95_ms": lat.get("p95_ms"),
        "p99_ms": lat.get("p99_ms"),
        "avg_ms": lat.get("avg_ms"),
        "median_ms": lat.get("p50_ms"),
        "max_ms": lat.get("max_ms"),
        "error_rate": snapshot.get("error_rate"),
    }
    return mapping.get(metric)


def _compare(actual: float, op: str, target: float) -> bool:
    if op == "<":
        return actual < target
    if op == "<=":
        return actual <= target
    if op == ">":
        return actual > target
    if op == ">=":
        return actual >= target
    return False


def evaluate(model: LoadModel, snapshot: dict) -> dict:
    """Return a structured verdict: each threshold checked, plus overall pass/fail."""
    checks = []
    for th in model.thresholds:
        actual = _metric_value(snapshot, th.metric)
        if actual is None:
            checks.append(
                {
                    "metric": th.metric,
                    "op": th.op,
                    "target": th.value,
                    "actual": None,
                    "passed": None,
                }
            )
            continue
        passed = _compare(actual, th.op, th.value)
        checks.append(
            {
                "metric": th.metric,
                "op": th.op,
                "target": th.value,
                "actual": round(actual, 4),
                "passed": passed,
            }
        )

    evaluable = [c for c in checks if c["passed"] is not None]
    overall = all(c["passed"] for c in evaluable) if evaluable else None

    return {
        "overall_passed": overall,
        "checks": checks,
    }
