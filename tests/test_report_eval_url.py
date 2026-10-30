"""Regression test: report citation check ignores numbers inside URLs/hosts/timestamps."""

from __future__ import annotations

from perfagent.evaluation.report_eval import evaluate_report

_SNAP = {"requests": 220, "error_rate": 0.0, "rps": 1.31,
         "latency": {"p95_ms": 1.96, "p99_ms": 2.36, "avg_ms": 1.3}}
_VERDICT = {"overall_passed": True, "checks": []}


def test_url_numbers_not_flagged():
    text = "Performance test passed for target http://127.0.0.1:8000. p95 was 1.96 ms."
    r = evaluate_report(text, _SNAP, _VERDICT)
    assert r.grounded
    assert "127.0" not in r.unsupported_numbers
    assert "8000" not in r.unsupported_numbers


def test_ip_port_not_flagged():
    text = "Ran against 10.0.4.21:9090 with 220 requests."
    r = evaluate_report(text, _SNAP, _VERDICT)
    assert r.grounded


def test_timestamp_not_flagged():
    text = "Run finished 2026-10-30T11:42:29 with error rate 0.00%."
    r = evaluate_report(text, _SNAP, _VERDICT)
    assert r.grounded


def test_real_hallucination_still_caught():
    text = "The system handled 220 requests but latency spiked to 999 ms."
    r = evaluate_report(text, _SNAP, _VERDICT)
    assert not r.grounded
    assert "999" in r.unsupported_numbers
