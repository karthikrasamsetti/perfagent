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
