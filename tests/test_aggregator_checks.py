"""Tests: failed checks/assertions count toward the error rate (not just HTTP status)."""

from __future__ import annotations

from perfagent.stats.aggregator import Aggregator


def _ontrac_like():
    """11 requests, all HTTP 200, but a content assertion fails each time."""
    agg = Aggregator()
    for _ in range(11):
        agg.add_point({"metric": "http_reqs", "data": {"value": 1, "tags": {"name": "get rates"}}})
        agg.add_point({"metric": "http_req_duration", "data": {"value": 288.0, "tags": {"name": "get rates"}}})
        agg.add_point({"metric": "http_req_failed", "data": {"value": 0, "tags": {"name": "get rates"}}})
        agg.add_point({"metric": "errors", "data": {"value": 1, "tags": {"name": "get rates"}}})
        agg.add_point({"metric": "checks", "data": {"value": 1, "tags": {"check": "status ok"}}})
        agg.add_point({"metric": "checks", "data": {"value": 0, "tags": {"check": "no Invalid Parameters"}}})
    return agg


def test_failed_checks_raise_error_rate():
    s = _ontrac_like().snapshot()
    # HTTP status was all 200, but checks failed -> error rate must NOT be 0
    assert s["error_rate"] == 1.0
    assert s["failed"] == 11


def test_checks_breakdown_surfaced():
    s = _ontrac_like().snapshot()
    names = {c["name"]: c for c in s["checks"]}
    assert names["no Invalid Parameters"]["failed"] == 11
    assert names["no Invalid Parameters"]["passed"] == 0
    assert names["status ok"]["passed"] == 11
    # failing checks sort first
    assert s["checks"][0]["failed"] > 0


def test_clean_run_zero_error_rate():
    agg = Aggregator()
    for _ in range(5):
        agg.add_point({"metric": "http_reqs", "data": {"value": 1, "tags": {"name": "x"}}})
        agg.add_point({"metric": "http_req_duration", "data": {"value": 100.0, "tags": {"name": "x"}}})
        agg.add_point({"metric": "http_req_failed", "data": {"value": 0, "tags": {"name": "x"}}})
        agg.add_point({"metric": "errors", "data": {"value": 0, "tags": {"name": "x"}}})
        agg.add_point({"metric": "checks", "data": {"value": 1, "tags": {"check": "ok"}}})
    s = agg.snapshot()
    assert s["error_rate"] == 0.0


def test_http_failures_still_count():
    agg = Aggregator()
    for i in range(4):
        agg.add_point({"metric": "http_reqs", "data": {"value": 1, "tags": {"name": "x"}}})
        agg.add_point({"metric": "http_req_failed", "data": {"value": 1 if i == 0 else 0, "tags": {"name": "x"}}})
    s = agg.snapshot()
    assert s["error_rate"] == 0.25   # 1 of 4 HTTP-failed
