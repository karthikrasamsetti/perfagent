"""Deterministic metrics aggregation — code owns every number.

Consumes k6's raw metric points and computes the live/final figures the UI shows:
request counts, error rate, throughput, and latency percentiles. No LLM touches
any of this. Percentiles use numpy for correctness.
"""

from __future__ import annotations

import time

import numpy as np


class Aggregator:
    def __init__(self) -> None:
        self._durations: list[float] = []   # http_req_duration values (ms)
        self._req_count = 0
        self._failed = 0
        self._checks_total = 0
        self._checks_passed = 0
        self._start = time.time()
        # per-endpoint (by k6 tag "name") latency + counts
        self._by_name: dict[str, dict] = {}

    def add_point(self, obj: dict) -> None:
        metric = obj.get("metric")
        data = obj.get("data", {})
        value = data.get("value")
        tags = data.get("tags", {}) or {}
        name = tags.get("name", "(unnamed)")

        if metric == "http_req_duration" and value is not None:
            self._durations.append(float(value))
            b = self._by_name.setdefault(name, {"durations": [], "count": 0, "failed": 0})
            b["durations"].append(float(value))
            b["count"] += 1

        elif metric == "http_reqs" and value is not None:
            self._req_count += int(value)

        elif metric == "http_req_failed" and value is not None:
            if value:
                self._failed += int(value)
                b = self._by_name.setdefault(name, {"durations": [], "count": 0, "failed": 0})
                b["failed"] += int(value)

        elif metric == "checks" and value is not None:
            self._checks_total += 1
            if value:
                self._checks_passed += 1

    def _pctl(self, arr: list[float], p: float) -> float:
        if not arr:
            return 0.0
        return round(float(np.percentile(arr, p)), 2)

    def snapshot(self) -> dict:
        elapsed = max(0.001, time.time() - self._start)
        durations = self._durations
        n = len(durations)
        error_rate = (self._failed / self._req_count) if self._req_count else 0.0

        per_endpoint = []
        for name, b in sorted(self._by_name.items()):
            d = b["durations"]
            per_endpoint.append(
                {
                    "name": name,
                    "requests": b["count"],
                    "failed": b["failed"],
                    "p95_ms": self._pctl(d, 95),
                    "avg_ms": round(sum(d) / len(d), 2) if d else 0.0,
                }
            )

        return {
            "elapsed_s": round(elapsed, 1),
            "requests": self._req_count,
            "failed": self._failed,
            "error_rate": round(error_rate, 4),
            "rps": round(self._req_count / elapsed, 2),
            "checks_total": self._checks_total,
            "checks_passed": self._checks_passed,
            "latency": {
                "samples": n,
                "avg_ms": round(sum(durations) / n, 2) if n else 0.0,
                "p50_ms": self._pctl(durations, 50),
                "p90_ms": self._pctl(durations, 90),
                "p95_ms": self._pctl(durations, 95),
                "p99_ms": self._pctl(durations, 99),
                "max_ms": round(max(durations), 2) if durations else 0.0,
            },
            "per_endpoint": per_endpoint,
        }