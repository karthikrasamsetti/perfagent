"""Baseline / regression — compare a run to the previous run of the same plan.

Deterministic: pulls the key metrics from the current snapshot and the stored
previous run, computes the change, and classifies each metric as better / worse /
same. "Worse" means higher latency/error rate or lower throughput.
"""

from __future__ import annotations

from dataclasses import dataclass


def metrics_from_snapshot(snapshot: dict) -> dict:
    """Pull the comparable key metrics out of an aggregator snapshot."""
    lat = snapshot.get("latency", {}) or {}
    return {
        "requests": int(snapshot.get("requests", 0) or 0),
        "error_rate": float(snapshot.get("error_rate", 0.0) or 0.0),
        "rps": float(snapshot.get("rps", 0.0) or 0.0),
        "p95_ms": float(lat.get("p95_ms", 0.0) or 0.0),
        "p99_ms": float(lat.get("p99_ms", 0.0) or 0.0),
        "avg_ms": float(lat.get("avg_ms", 0.0) or 0.0),
    }


# For each metric: does a HIGHER value mean worse performance?
_HIGHER_IS_WORSE = {
    "error_rate": True,
    "p95_ms": True,
    "p99_ms": True,
    "avg_ms": True,
    "rps": False,       # higher throughput is better
    "requests": None,   # informational only
}

# relative change below this is treated as "same" (noise)
_NOISE = 0.05  # 5%


@dataclass
class MetricDelta:
    metric: str
    current: float
    previous: float
    pct_change: float        # (current - previous) / previous
    direction: str           # "better" | "worse" | "same" | "n/a"


def _classify(metric: str, cur: float, prev: float) -> MetricDelta:
    if prev == 0:
        pct = 0.0 if cur == 0 else 1.0
    else:
        pct = (cur - prev) / abs(prev)

    higher_worse = _HIGHER_IS_WORSE.get(metric)
    if higher_worse is None:
        direction = "n/a"
    elif abs(pct) < _NOISE:
        direction = "same"
    elif (pct > 0 and higher_worse) or (pct < 0 and not higher_worse):
        direction = "worse"
    else:
        direction = "better"
    return MetricDelta(metric, cur, prev, round(pct, 4), direction)


def compare(current: dict, previous: dict) -> dict:
    """Compare current metrics to a previous run's metrics. Returns a summary dict."""
    deltas = []
    worse = []
    for m in ("error_rate", "p95_ms", "p99_ms", "avg_ms", "rps"):
        d = _classify(m, float(current.get(m, 0) or 0), float(previous.get(m, 0) or 0))
        deltas.append(d)
        if d.direction == "worse":
            worse.append(d)

    # overall: any regression?
    regressed = len(worse) > 0
    # headline = the worst regression, or an all-clear
    if worse:
        top = max(worse, key=lambda d: abs(d.pct_change))
        headline = (f"Regression: {_label(top.metric)} got "
                    f"{abs(top.pct_change)*100:.0f}% worse "
                    f"({_fmt(top.metric, top.previous)} → {_fmt(top.metric, top.current)})")
    else:
        headline = "No regression vs. the previous run."

    return {
        "has_previous": True,
        "regressed": regressed,
        "headline": headline,
        "deltas": [
            {"metric": d.metric, "label": _label(d.metric),
             "current": d.current, "previous": d.previous,
             "pct_change": d.pct_change, "direction": d.direction,
             "current_fmt": _fmt(d.metric, d.current),
             "previous_fmt": _fmt(d.metric, d.previous)}
            for d in deltas
        ],
    }


def no_baseline() -> dict:
    return {"has_previous": False, "regressed": False,
            "headline": "First run for this plan — no previous run to compare against.",
            "deltas": []}


_LABELS = {"error_rate": "Error rate", "p95_ms": "p95 latency",
           "p99_ms": "p99 latency", "avg_ms": "Avg latency", "rps": "Throughput"}


def _label(m: str) -> str:
    return _LABELS.get(m, m)


def _fmt(metric: str, v: float) -> str:
    if metric == "error_rate":
        return f"{v*100:.2f}%"
    if metric == "rps":
        return f"{v:.2f}/s"
    return f"{v:.0f} ms"
