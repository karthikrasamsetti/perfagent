"""Reporting projection + coverage logic. No LLM, no k6; runs offline."""
from datetime import datetime, timezone

import pytest

from perfagent.db.models import RunRecord, RunStatus
from perfagent.reporting.service import Role, project


@pytest.fixture
def run() -> RunRecord:
    return RunRecord(
        run_id="r-1", scenario="checkout", environment="prod",
        target_url="https://x", load_tool="k6", status=RunStatus.PASSED,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        p50_ms=90, p90_ms=200, p95_ms=250, p99_ms=400,
        error_rate=0.01, rps=120, max_vus=50, total_requests=10_000,
        verdict="PASS",
    )


def test_executive_hides_internals(run):
    v = project(run, Role.EXECUTIVE)
    assert "verdict" in v and "p95_ms" in v
    assert "target_url" not in v and "total_requests" not in v


def test_qa_lead_sees_coverage_and_thresholds(run):
    v = project(run, Role.QA_LEAD)
    assert {"p99_ms", "coverage", "thresholds"} <= set(v)
    assert "ai_narrative" not in v   # narrative is engineer-only


def test_engineer_sees_all(run):
    v = project(run, Role.ENGINEER)
    assert "target_url" in v and "ai_narrative" in v


def test_viewer_minimal(run):
    v = project(run, Role.VIEWER)
    assert set(v) == {"run_id", "scenario", "status", "verdict", "p95_ms"}


def test_status_serialized_to_str(run):
    assert project(run, Role.QA_LEAD)["status"] == "passed"


def test_download_renders_saved_journey_checks_and_timing_without_inventing_values():
    from perfagent.analyzer.narrator import Narrative
    from perfagent.analyzer.report import render_report_html

    report = render_report_html(
        target="https://fixture.test",
        tool="k6",
        execution={"test_name": "Checkout", "environment": "staging"},
        snapshot={
            "requests": 2, "bytes_received": 1024,
            "per_endpoint": [{"name": "Order", "requests": 2, "failed": 1,
                              "p95_ms": 250, "status_codes": {"200": 1, "503": 1},
                              "timing_phases": {"waiting": {"avg_ms": 90, "p95_ms": 110}}}],
            "per_journey": [{"name": "Checkout journey", "requests": 2, "failed": 1}],
            "checks": [{"name": "order.id exists", "passed": 1, "failed": 1}],
        },
        verdict={"overall_passed": False},
        narrative=Narrative(headline="Failed", summary="One request failed."),
    )
    assert "Checkout journey" in report
    assert "order.id exists" in report
    assert "503: 1" in report
    assert "waiting" in report and "110" in report
    assert "Bytes received 1024" in report
    assert "Environment staging" in report
    assert "Unavailable" in report and "0.00%" not in report


def test_report_leads_with_saved_explanation_and_orders_breaches_first():
    from perfagent.analyzer.narrator import Narrative
    from perfagent.analyzer.report import render_report_html
    from perfagent.analyzer.report_evidence import report_evidence

    verdict = {"overall_passed": False, "checks": [
        {"metric": "error_rate", "op": "<", "target": .01, "actual": 0, "passed": True},
        {"metric": "p95_ms", "op": "<=", "target": 300, "actual": 420, "passed": False},
    ]}
    payload = {"verdict": verdict, "execution": {"target_request_rate": 15},
               "snapshot": {"rps": 12.8}, "status": "finished"}
    evidence = report_evidence(payload)
    assert [rule["metric"] for rule in evidence["thresholds"]] == ["p95_ms", "error_rate"]
    assert evidence["passed_count"] == 1
    assert evidence["metrics"]["target_rps"] == 15

    html = render_report_html(
        target="https://fixture.test", tool="k6", snapshot=payload["snapshot"],
        execution={**payload["execution"], "planned_phases": [
            {"label": "Ramp up", "start_s": 0, "end_s": 5},
            {"label": "Steady state", "start_s": 5, "end_s": 15},
        ]}, status="finished", verdict=verdict,
        samples=[{"t": 15, "rps": 12.8, "p95": 420, "dropped_iterations": 2},
                 {"t": 5, "rps": 10.0, "p95": 300, "dropped_iterations": 0}],
        narrative=Narrative(headline="Latency limit breached", summary="p95 reached 420 ms."),
    )
    assert html.index("What happened") < html.index("p95 reached 420 ms.") < html.index("Threshold results")
    assert html.index("<td>p95_ms</td>") < html.index("<td>error_rate</td>")
    assert "12.8 / 15" in html
    assert "<td>15</td><td>12.8</td><td>420</td><td>Unavailable</td>" in html
    assert "Planned phases · Ramp up 0–5 s" in html and 'class="phase-line"' in html
    assert "<figcaption>p95 latency (ms)</figcaption>" in html
    assert 'href="#run-timeline">First recorded dropped iterations at 15 s (2 cumulative).' in html
    assert 'class="phase-line drop-line"' in html
