import json

import pytest

from perfagent.ci.release_gate import gate_report, main


@pytest.fixture
def report():
    return {
        "status": "finished",
        "execution": {"mode": "full", "environment": "staging", "release_label": "v2.4"},
        "verdict": {"overall_passed": True},
        "release_readiness": {"status": "ready"},
    }


@pytest.mark.parametrize("status,code", [("ready", 0), ("blocked", 1), ("needs_evidence", 2), ("unknown", 2)])
def test_gate_exit_status(tmp_path, report, status, code):
    report["release_readiness"]["status"] = status
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert main([str(path), "--environment", "staging", "--release", "v2.4"]) == code


def test_gate_requires_a_matching_full_run(report):
    assert gate_report(report, release="old-release") == 2
    assert gate_report(report, environment="production") == 2
    report["status"] = "stopped"
    assert gate_report(report) == 2
    report["status"] = "finished"
    report["execution"]["mode"] = "smoke"
    assert gate_report(report) == 2
    report["execution"]["mode"] = "full"
    report["verdict"]["overall_passed"] = None
    assert gate_report(report) == 2


def test_missing_or_malformed_report_fails_closed(tmp_path):
    assert main([str(tmp_path / "missing.json")]) == 2
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    assert main([str(path)]) == 2
    assert gate_report([]) == 2
