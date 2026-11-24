"""Compare target-scoped Prometheus measurements before and during a k6 run."""

from math import isfinite
from statistics import fmean

import httpx

from perfagent.config import get_settings


def correlate(target: str, start: float | None, end: float | None) -> dict | None:
    settings = get_settings()
    if (not start or not end or end < start or not settings.perfagent_prometheus_url
            or not settings.perfagent_prometheus_queries
            or target.rstrip("/") != settings.perfagent_observability_target.rstrip("/")):
        return None

    token = settings.perfagent_prometheus_token.get_secret_value()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    endpoint = settings.perfagent_prometheus_url.rstrip("/") + "/api/v1/query_range"
    baseline_start = start - 120
    results = []
    with httpx.Client(headers=headers, timeout=3.0) as client:
        for name, query in settings.perfagent_prometheus_queries.items():
            result = {"name": name, "baseline_mean": None, "run_mean": None}
            try:
                response = client.get(endpoint, params={
                    "query": query, "start": baseline_start, "end": end,
                    "step": max(1, (end - baseline_start) / 600),
                })
                response.raise_for_status()
                series = response.json()["data"]["result"]
                if len(series) == 1:
                    baseline, during = [], []
                    for timestamp, raw in series[0]["values"]:
                        value = float(raw)
                        if isfinite(value) and baseline_start <= timestamp <= end:
                            (baseline if timestamp < start else during).append(value)
                    result["baseline_mean"] = fmean(baseline) if baseline else None
                    result["run_mean"] = fmean(during) if during else None
            except (httpx.HTTPError, httpx.InvalidURL, ValueError, KeyError, TypeError):
                pass
            results.append(result)
    return {"baseline_start_ts": baseline_start, "run_start_ts": start, "run_end_ts": end,
            "metrics": results}
