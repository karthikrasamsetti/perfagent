"""Presentation evidence derived from saved run measurements."""


def report_evidence(payload: dict) -> dict:
    verdict = payload.get("verdict") or {}
    checks = list(verdict.get("checks") or [])
    ordered = sorted(checks, key=lambda check: (
        0 if check.get("passed") is False else 1 if check.get("passed") is None else 2
    ))
    execution = payload.get("execution") or {}
    snapshot = payload.get("snapshot") or {}
    measured = snapshot.get("latency") or {}
    status = payload.get("status")
    return {
        "thresholds": ordered,
        "passed_count": sum(check.get("passed") is True for check in checks),
        "failed_count": sum(check.get("passed") is False for check in checks),
        "total_thresholds": len(checks),
        "partial": bool(status and status != "finished"),
        "metrics": {
            "requests": snapshot.get("requests"),
            "rps": snapshot.get("rps"),
            "target_rps": execution.get("target_request_rate") if not execution.get("script_edited") else None,
            "p95_ms": measured.get("p95_ms"),
            "error_rate": snapshot.get("error_rate"),
            "dropped_iterations": snapshot.get("dropped_iterations"),
        },
    }
