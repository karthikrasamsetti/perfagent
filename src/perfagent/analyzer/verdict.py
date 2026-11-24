"""Deterministic verdict — code decides pass/fail, never the LLM.

Compares a run's actual metrics (from the aggregator snapshot) against the plan's
thresholds and returns a structured verdict. Every number and every pass/fail here
is computed in code.

FAIL-CLOSED RULE: if a threshold cannot be evaluated (unknown metric, or the metric
is missing from the run snapshot), the overall verdict is never PASS. It becomes
INCONCLUSIVE. A performance test must never report green when it could not actually
check the criterion.
"""

from __future__ import annotations

import re
from decimal import Decimal

from perfagent.contracts.load_model import LoadModel

# The metrics the verdict knows how to read from a snapshot.
_KNOWN_METRICS = {
    "p50_ms", "p90_ms", "p95_ms", "p99_ms", "avg_ms", "median_ms", "max_ms",
    "error_rate",
}


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
    """Return a structured verdict: each threshold checked, plus overall pass/fail.

    overall_passed is:
      True   — there were thresholds, all were evaluable, and all passed
      False  — at least one evaluable threshold failed
      None   — no thresholds, OR at least one threshold could not be evaluated
               (unknown metric / missing from the run). Fail-closed: never PASS.
    """
    checks = []
    had_unevaluable = False

    for th in model.thresholds:
        known = th.metric in _KNOWN_METRICS
        actual = _metric_value(snapshot, th.metric) if known else None

        if not known:
            # unknown metric name — we cannot check this criterion
            had_unevaluable = True
            checks.append({
                "metric": th.metric, "op": th.op, "target": th.value,
                "actual": None, "passed": None,
                "reason": "unknown metric — cannot evaluate",
            })
            continue

        if actual is None:
            # known metric but not present in the run snapshot
            had_unevaluable = True
            checks.append({
                "metric": th.metric, "op": th.op, "target": th.value,
                "actual": None, "passed": None,
                "reason": "metric missing from run — cannot evaluate",
            })
            continue

        passed = _compare(actual, th.op, th.value)
        checks.append({
            "metric": th.metric, "op": th.op, "target": th.value,
            "actual": round(actual, 4), "passed": passed, "reason": "",
        })

    passed_checks = [c for c in checks if c["passed"] is not None]

    if not model.thresholds:
        overall = None                       # nothing to check
    elif had_unevaluable:
        overall = None                       # FAIL-CLOSED: cannot certify PASS
    elif all(c["passed"] for c in passed_checks):
        overall = True
    else:
        overall = False

    return {
        "overall_passed": overall,
        "has_unevaluable": had_unevaluable,
        "checks": checks,
    }


def evaluate_k6_summary(metrics: dict) -> dict:
    """Read the exact threshold expressions and outcomes from k6's summary export."""
    checks = []
    for metric, summary in metrics.items():
        for expression, failed in summary.get("thresholds", {}).items():
            match = re.fullmatch(r"(.+?)\s*(<=|>=|==|!=|<|>)\s*([-+0-9.eE]+)", expression)
            if not match:
                checks.append({"metric": f"{metric}: {expression}", "op": "", "target": None,
                               "actual": None, "passed": not failed, "reason": ""})
                continue
            aggregation, op, value = match.groups()
            aggregation = aggregation.strip()
            label = f"{metric} {aggregation}"
            if metric == "http_req_duration":
                label = {"med": "p50_ms", "p(50)": "p50_ms", "p(90)": "p90_ms",
                         "p(95)": "p95_ms", "p(99)": "p99_ms", "avg": "avg_ms",
                         "max": "max_ms"}.get(aggregation, label)
            elif metric in {"errors", "http_req_failed"} and aggregation == "rate":
                label = "error_rate"
            actual = summary.get("value" if aggregation == "rate" and "passes" in summary
                                 else aggregation)
            checks.append({"metric": label, "op": op, "target": float(value), "actual": actual,
                           "passed": not failed, "reason": ""})
    return {"checks": checks, "has_unevaluable": False,
            "overall_passed": all(check["passed"] for check in checks) if checks else None}



def format_threshold_value(metric: str, value: float | None) -> str:
    if value is None:
        return "Unavailable"
    if metric == "error_rate":
        return f"{(Decimal(str(value)) * 100).normalize():f}%"
    number = str(value).removesuffix(".0")
    return f"{number} ms" if metric.endswith("_ms") else number
