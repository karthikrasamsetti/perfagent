"""Reports and execution versions remain correct across retries and restarts."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from perfagent.contracts.load_model import Assertion, HttpMethod, LoadModel
from perfagent.db.models import Base, DataFileRow, PlanRow, RunResultRow, ScriptRow, ScriptSnapshotRow
from perfagent.runner.k6_runner import RunState


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from perfagent.api import app as api
    from perfagent.db import models
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(models, "get_engine", lambda *a, **k: engine)
    monkeypatch.setattr(api, "build_provider", lambda: None)
    monkeypatch.setattr(api, "k6_available", lambda: True)
    with Session(engine) as s:
        model = LoadModel.model_validate({
            "target_base_url": "http://fixture.test", "environment": "staging",
            "scenarios": [{"name": "browse", "steps": [{"name": "products", "path": "/products"}]}],
            "load_profile": {"stages": [{"duration_seconds": 30, "target_users": 3}]},
            "thresholds": [{"metric": "p95_ms", "op": "<", "value": 500}],
        })
        s.add(PlanRow(id="plan", target_base_url=model.target_base_url, goal="fixture",
                      load_model_json=model.model_dump_json()))
        s.commit()
    client = TestClient(api.app)
    generated = client.post('/api/plan/plan/generate', json={"tool": "k6"})
    assert generated.status_code == 200, generated.text
    script_id = generated.json()['script_id']
    yield client, engine, api, script_id, model
    engine.dispose()


def finished(api, script_id, monkeypatch, *, status="finished"):
    run = RunState(run_id="original-run", script_id=script_id, tool="k6", target="http://fixture.test")
    run.status = status
    run.load_model_json = LoadModel.model_validate({
        "target_base_url": run.target,
        "scenarios": [{"name": "browse", "steps": [{"name": "products", "path": "/products"}]}],
        "load_profile": {"stages": [{"duration_seconds": 30, "target_users": 3}]},
        "thresholds": [{"metric": "p95_ms", "op": "<", "value": 500}],
    }).model_dump_json()
    run.snapshot = {"requests": 20, "rps": 2, "error_rate": 0,
                    "latency": {"samples": 20, "p95_ms": 100, "p99_ms": 120, "avg_ms": 80},
                    "per_endpoint": [], "checks": []}
    run.samples = [{"t": 1, "p95": 100, "rps": 2, "err": 0}]
    run.metadata = {"workload_version": "v1", "environment": "staging"}
    monkeypatch.setattr(api, "get_run", lambda rid: run if rid == run.run_id else None)
    return run


def test_identical_generation_reuses_latest_version_and_changes_preserve_history(setup):
    client, _, _, script_id, model = setup
    repeated = client.post("/api/plan/plan/generate", json={"tool": "k6"})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["script_id"] == script_id and repeated.json()["reused"] is True
    model.thresholds[0].value = 350
    changed = client.post("/api/plan/plan/generate", json={"tool": "k6", "load_model": model.model_dump(mode="json")})
    assert changed.status_code == 200, changed.text
    assert changed.json()["script_id"] != script_id and changed.json()["reused"] is False
    versions = client.get("/api/plans/plan").json()["scripts"]
    assert [version["script_id"] for version in versions] == [script_id, changed.json()["script_id"]]
    assert all(version["source"] == "generated" for version in versions)
    assert client.get(f"/api/scripts/{script_id}/download").status_code == 200


def test_report_retries_do_not_duplicate_and_download_survives_restart(setup, monkeypatch):
    client, engine, api, script_id, _ = setup
    run = finished(api, script_id, monkeypatch)
    first = client.get(f'/api/runs/{run.run_id}/report')
    assert first.status_code == 200, first.text
    assert first.json()['snapshot']['requests'] == 20
    assert first.json()['samples'] == run.samples
    assert client.get(f'/api/runs/{run.run_id}/report').json() == first.json()
    with Session(engine) as s:
        assert s.query(RunResultRow).count() == 1
    monkeypatch.setattr(api, "get_run", lambda rid: None)
    assert client.get(f'/api/runs/{run.run_id}/report').json() == first.json()
    download = client.get(f'/api/runs/{run.run_id}/report/download')
    assert download.status_code == 200
    assert '100' in download.text and 'http://fixture.test' in download.text


def test_legacy_saved_row_can_download_by_saved_or_original_id(setup, monkeypatch):
    client, engine, api, script_id, _ = setup
    finished(api, script_id, monkeypatch)
    payload = client.get('/api/runs/original-run/report').json()
    with Session(engine) as s:
        row = s.get(RunResultRow, 'original-run')
        row.id = 'legacy-saved-id'
        s.commit()
    monkeypatch.setattr(api, "get_run", lambda rid: None)
    assert client.get('/api/runs/legacy-saved-id/report/download').status_code == 200
    assert client.get('/api/runs/original-run/report').json() == payload
    assert client.get('/api/runs/legacy-saved-id/saved-report').status_code == 200


def test_stopped_run_is_not_a_pass(setup, monkeypatch):
    client, _, api, script_id, _ = setup
    finished(api, script_id, monkeypatch, status='stopped')
    report = client.get('/api/runs/original-run/report').json()
    assert report['status'] == 'stopped'
    assert report['verdict']['overall_passed'] is None


def test_generation_freezes_plan_and_dataset_versions(setup, monkeypatch):
    client, engine, api, _, model = setup
    with Session(engine) as s:
        s.add(DataFileRow(id='data-a', filename='users.csv', content='name\nAlice\n',
                          source_format='csv', columns_csv='name', row_count=1))
        s.commit()
    result = client.post('/api/plan/plan/generate', json={"tool": "k6", "data_file_id": "data-a"})
    script_id = result.json()['script_id']
    with Session(engine) as s:
        s.add(DataFileRow(id='data-b', filename='users.csv', content='name\nBob\n',
                          source_format='csv', columns_csv='name', row_count=1))
        model.target_base_url = 'http://changed.test'
        s.get(PlanRow, 'plan').load_model_json = model.model_dump_json()
        s.commit()
    captured = {}
    def start(**kwargs):
        captured.update(kwargs)
        return RunState(run_id=kwargs['run_id'], script_id=kwargs['script_id'],
                        target=kwargs['target'], tool='k6')
    monkeypatch.setattr(api, "start_run", start)
    assert client.post(f'/api/scripts/{script_id}/run').status_code == 200
    assert captured['target'] == 'http://fixture.test'
    assert captured['data_content'] == 'name\nAlice\n'


def test_smoke_uses_separate_bounded_script_and_does_not_change_full_version(setup, monkeypatch):
    client, engine, api, script_id, model = setup
    captured = {}
    def start(**kwargs):
        captured.update(kwargs)
        return RunState(run_id=kwargs['run_id'], script_id=kwargs['script_id'], target=kwargs['target'], tool='k6')
    monkeypatch.setattr(api, "start_run", start)
    r = client.post(f'/api/scripts/{script_id}/run', json={"smoke": True})
    assert r.status_code == 200, r.text
    assert captured['script_id'] != script_id
    assert "duration: '10s'" in captured['content'] and "gracefulStop: '0s'" in captured['content']
    with Session(engine) as s:
        original = LoadModel.model_validate_json(s.get(ScriptSnapshotRow, script_id).load_model_json)
        assert original.load_profile.total_seconds == 30


def test_filters_search_all_history_and_paginate(setup):
    client, engine, _, _, _ = setup
    with Session(engine) as s:
        for i in range(120):
            s.add(RunResultRow(id=f'r{i}', plan_id='plan', target_base_url='http://needle.test' if i == 0 else 'http://other.test',
                              verdict='pass', created_at=datetime(2026, 11, 1, 0, 0, i % 60)))
        s.commit()
    r = client.get('/api/reporting/runs?role=engineer&target=needle&limit=50').json()
    assert r['total'] == 1 and r['runs'][0]['run_id'] == 'r0'
    r = client.get('/api/reporting/runs?role=engineer&limit=50&offset=100').json()
    assert r['total'] == 120 and len(r['runs']) == 20
    assert client.get('/api/reporting/runs?role=viewer&target=needle').status_code == 400
    assert client.get('/api/reporting/runs?since=2026-11-02T00:00:00Z').json()['total'] == 0


def test_arrival_rate_preserves_requested_total_and_rejects_other_tools(setup):
    _, _, _, _, model = setup
    from perfagent.generator import render
    model.scenarios = [model.scenarios[0].model_copy(update={"name": f"journey{i}"}) for i in range(3)]
    model.load_profile.arrival_rate = 5
    _, script = render(model, 'k6')
    import re
    assert sum(map(int, re.findall(r'\brate: (\d+)', script))) == 5
    assert sum(map(int, re.findall(r'preAllocatedVUs: (\d+)', script))) == 10
    assert "executor: 'constant-arrival-rate'" in script
    assert '    sleep(' not in script
    with pytest.raises(ValueError, match='k6 only'):
        render(model, 'locust')
    model.load_profile.arrival_rate = 1
    with pytest.raises(ValueError, match='number of journeys'):
        render(model, 'k6')


def test_readiness_does_not_send_traffic_and_metrics_track_dropped(setup):
    client, _, _, script_id, _ = setup
    result = client.get(f'/api/scripts/{script_id}/readiness')
    assert result.status_code == 200 and result.json()['smoke_supported']
    assert len(result.json()['checks']) == 4
    from perfagent.stats import Aggregator
    agg = Aggregator()
    agg.add_point({"metric": "iterations", "data": {"value": 3}})
    agg.add_point({"metric": "dropped_iterations", "data": {"value": 2}})
    assert agg.snapshot()['iterations'] == 3
    assert agg.snapshot()['dropped_iterations'] == 2


def test_selected_baseline_requires_matching_finished_workload(setup, monkeypatch):
    client, engine, api, script_id, _ = setup
    run = finished(api, script_id, monkeypatch)
    with Session(engine) as s:
        run.metadata = json.loads(s.get(ScriptSnapshotRow, script_id).metadata_json)
    assert client.get('/api/runs/original-run/report').status_code == 200
    monkeypatch.setattr(api, "start_run", lambda **kw: RunState(
        run_id=kw['run_id'], script_id=kw['script_id'], target=kw['target'], tool='k6'))
    assert client.post(f'/api/scripts/{script_id}/run', json={"baseline_id": "original-run"}).status_code == 200
    with Session(engine) as s:
        row = s.get(RunResultRow, 'original-run')
        payload = json.loads(row.report_json)
        payload['status'] = 'stopped'
        row.report_json = json.dumps(payload)
        s.commit()
    assert client.post(f'/api/scripts/{script_id}/run', json={"baseline_id": "original-run"}).status_code == 400


def test_automatic_baseline_skips_stopped_results_and_smoke_is_not_latest_full(setup, monkeypatch):
    client, _, api, script_id, _ = setup
    run = finished(api, script_id, monkeypatch)
    assert client.get('/api/runs/original-run/report').status_code == 200
    run.run_id, run.status = 'partial-run', 'stopped'
    assert client.get('/api/runs/partial-run/report').status_code == 200
    run.run_id, run.status = 'next-run', 'finished'
    result = client.get('/api/runs/next-run/report')
    assert result.status_code == 200
    assert result.json()['baseline_id'] == 'original-run'
    monkeypatch.setattr(api, "start_run", lambda **kw: RunState(
        run_id=kw['run_id'], script_id=kw['script_id'], target=kw['target'], tool='k6'))
    assert client.post(f'/api/scripts/{script_id}/run', json={"smoke": True}).status_code == 200
    scripts = client.get('/api/plans/plan').json()['scripts']
    assert any(script['mode'] == 'smoke' for script in scripts)
    assert [script for script in scripts if script['mode'] != 'smoke'][-1]['script_id'] == script_id


def test_edited_k6_preflight_and_report_keep_plan_and_use_actual_thresholds(setup):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from time import monotonic, sleep

    from perfagent.runner.k6_binary import find_k6

    if find_k6() is None:
        pytest.skip("Requires an installed k6.")

    client, _, _, _, model = setup
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, self.headers.get("Authorization")))
            payload = (self.server.payload if isinstance(self.server.payload, bytes)
                       else json.dumps(self.server.payload).encode())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.payload = {"pizza": {"name": "Margherita"}}
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        model.target_base_url = f"http://127.0.0.1:{server.server_port}"
        model.headers = {"Authorization": "Token fixture"}
        scenario = model.scenarios[0]
        scenario.think_time.min_seconds = scenario.think_time.max_seconds = 0
        step = scenario.steps[0]
        step.method, step.path = HttpMethod.POST, "/api/pizza"
        step.assertions = [Assertion(kind="json_path", op="exists", path="pizza.name")]
        response = client.post("/api/plan/plan/generate", json={"load_model": model.model_dump()})
        assert response.status_code == 200, response.text
        source = response.json()
        content = source["content"] + """
options.scenarios.browse = { executor: 'shared-iterations', vus: 1, iterations: 1, exec: 'browse' };
options.thresholds = { http_req_duration: ['p(95)<=500'], errors: ['rate<0.01'] };
"""
        edited = client.post(f"/api/scripts/{source['script_id']}/edit", json={"content": content})
        assert edited.status_code == 200, edited.text
        assert edited.json()["plan_id"] == "plan"
        script_id = edited.json()["script_id"]
        assert script_id != source["script_id"]
        preflight = client.post("/api/preflight", json={"script_id": script_id})
        assert preflight.json()["all_ok"], preflight.text
        assert requests == [("/api/pizza", "Token fixture")]

        for invalid_payload in ({"pizza": {}}, b"not JSON"):
            server.payload = invalid_payload
            assert not client.post("/api/preflight", json={"script_id": script_id}).json()["all_ok"]
        server.payload = {"pizza": {"name": "Margherita"}}

        response = client.post(f"/api/scripts/{script_id}/run", json={"release_label": "demo-release"})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        deadline = monotonic() + 15
        while monotonic() < deadline:
            if client.get(f"/api/runs/{run_id}").json()["status"] not in {"starting", "preparing", "running"}:
                break
            sleep(0.05)
        report = client.get(f"/api/runs/{run_id}/report").json()
        assert report["plan_id"] == "plan"
        assert report["execution"]["environment"] == "staging"
        assert report["execution"]["release_label"] == "demo-release"
        assert report["execution"]["script_edited"] is True
        assert report["execution"]["verification"]["script_id"] == script_id
        assert report["execution"]["verification"]["all_ok"] is False
        assert report["snapshot"]["per_endpoint"][0]["status_codes"] == {"200": 1}
        assert report["snapshot"]["per_journey"][0]["requests"] == 1
        assert report["execution"]["run_start_ts"] <= report["execution"]["run_end_ts"]
        assert report["verdict"]["overall_passed"] is True, report
        assert {(c["metric"], c["op"], c["target"]) for c in report["verdict"]["checks"]} == {
            ("p95_ms", "<=", 500), ("error_rate", "<", 0.01),
        }
        assert "Error rate < 1%" in report["narrative"]["summary"]
        assert "p95 <= 500 ms" in report["narrative"]["summary"]
        assert report["snapshot"]["per_endpoint"][0]["timing_phases"]["waiting"]["avg_ms"] >= 0
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_run_capacity_returns_rate_limit_status(setup, monkeypatch):
    client, _, api, script_id, _ = setup
    from perfagent.runner.k6_runner import RunCapacityExceeded

    def reject_run(**kwargs):
        raise RunCapacityExceeded("All k6 run slots are busy.")

    monkeypatch.setattr(api, "start_run", reject_run)
    response = client.post(f"/api/scripts/{script_id}/run")
    assert response.status_code == 429
    assert "slots are busy" in response.json()["detail"]


def test_verification_is_saved_only_for_the_exact_script_version(setup, monkeypatch):
    client, _, api, script_id, _ = setup
    result = {"mode": "script", "all_ok": True, "journeys": [{"name": "browse"}], "message": "Passed"}
    monkeypatch.setattr(api, "preflight_script", lambda *args: result)

    original = client.post("/api/preflight", json={"script_id": script_id})
    assert original.status_code == 200, original.text
    original = original.json()
    readiness = client.get(f"/api/scripts/{script_id}/readiness").json()
    assert readiness["verification"] == {
        "script_id": script_id, "verified_at": original["verified_at"],
        "all_ok": True, "journeys_checked": 1,
    }

    script = client.get(f"/api/scripts/{script_id}/download").text
    edited = client.post(f"/api/scripts/{script_id}/edit", json={"content": script + "\n// edited\n"})
    assert edited.status_code == 200, edited.text
    edited_id = edited.json()["script_id"]
    assert edited_id != script_id
    assert client.get(f"/api/scripts/{edited_id}/readiness").json()["verification"] is None

    result.update(all_ok=False, message="Failed")
    failed = client.post("/api/preflight", json={"script_id": script_id})
    assert failed.status_code == 200, failed.text
    assert client.get(f"/api/scripts/{script_id}/readiness").json()["verification"]["all_ok"] is False


def test_history_overview_covers_all_matching_runs_and_preserves_viewer_fields(setup):
    client, engine, _, _, _ = setup
    with Session(engine) as s:
        for index in range(3):
            s.add(RunResultRow(
                id=f"overview-{index}", plan_id="plan", target_base_url="http://fixture.test",
                verdict="fail" if index == 1 else "pass", requests=100 + index,
                p95_ms=100 + index * 20, error_rate=.01,
                created_at=datetime(2026, 11, 19, 6, index),
            ))
        s.add(RunResultRow(id="outside", plan_id="another", target_base_url="http://unrelated.test",
                           requests=200, p95_ms=999, verdict="fail"))
        s.commit()

    def overview(offset):
        response = client.get("/api/reporting/runs", params={
            "plan_id": "plan", "role": "viewer", "include_overview": "true",
            "limit": 1, "offset": offset,
        })
        assert response.status_code == 200, response.text
        return response.json()

    first, second = overview(0), overview(1)
    assert first["runs"] != second["runs"]
    assert first["overview"] == second["overview"]
    totals = first["overview"]
    assert (totals["total"], totals["passed"], totals["failed"], totals["requests"]) == (3, 2, 1, 303)
    assert totals["worst_p95_ms"] == 140
    assert totals["latest"]["run_id"] == "overview-2"
    assert [point["p95_ms"] for point in totals["trend"]] == [100, 120, 140]
    assert all("error_rate" not in point for point in totals["trend"])
    assert totals["outcomes"] == [{"day": "2026-11-19", "pass": 2, "fail": 1, "inconclusive": 0}]


def test_history_filters_environment_and_release_before_aggregation(setup):
    client, engine, _, _, _ = setup
    with Session(engine) as s:
        for index, (environment, release) in enumerate([
            ("staging", "v2"), ("staging", "v1"), ("production", "v2"),
        ]):
            payload = {"execution": {"environment": environment, "release_label": release}}
            s.add(RunResultRow(id=f"filtered-{index}", plan_id="plan", target_base_url="http://fixture.test",
                               verdict="pass", report_json=json.dumps(payload)))
        s.commit()
    params = {"plan_id": "plan", "environment": "STAGING", "release_label": "v2",
              "role": "engineer", "include_overview": "true"}
    result = client.get("/api/reporting/runs", params=params).json()
    assert result["total"] == result["overview"]["total"] == 1
    assert result["runs"][0]["run_id"] == "filtered-0"
    assert client.get("/api/reporting/runs", params={**params, "role": "viewer"}).status_code == 400


@pytest.mark.parametrize(("environment", "status", "requests", "visible"), [
    ("staging", "finished", 20, True),
    ("production", "finished", 20, False),
    ("staging", "stopped", 20, False),
    ("staging", "finished", 0, False),
])
def test_dashboard_regression_requires_comparable_measurements(
    setup, environment, status, requests, visible,
):
    client, engine, _, _, _ = setup
    with Session(engine) as s:
        for index, run_id in enumerate(("baseline", "latest")):
            report = {
                "status": status if index else "finished",
                "baseline_id": "baseline" if index else None,
                "execution": {"workload_version": "v1",
                              "environment": environment if index else "staging"},
                "snapshot": {"requests": requests if index else 20,
                             "error_rate": .02 if index else 0,
                             "latency": {"p95_ms": 140 if index else 100}},
            }
            s.add(RunResultRow(id=run_id, plan_id="plan", target_base_url="http://fixture.test",
                               verdict="pass", created_at=datetime(2026, 11, 19, 6, index),
                               report_json=json.dumps(report)))
        s.commit()

    for role in ("viewer", "engineer"):
        response = client.get("/api/reporting/runs", params={
            "plan_id": "plan", "role": role, "include_overview": "true",
        })
        assert response.status_code == 200, response.text
        overview = response.json()["overview"]
        assert overview["attention"] is None
        alert = overview["regression"]
        if not visible:
            assert alert is None
            continue
        assert alert["baseline_id"] == "baseline" and alert["run"]["verdict"] == "pass"
        assert alert["changes"][-1] == {
            "label": "p95 latency", "metric": "p95_ms",
            "previous_fmt": "100 ms", "current_fmt": "140 ms",
        }
        assert [change["metric"] for change in alert["changes"]] == (
            ["p95_ms"] if role == "viewer" else ["error_rate", "p95_ms"]
        )


@pytest.mark.parametrize("p95,workload,status", [
    (240, "v1", "ready"),
    (256, "v1", "blocked"),
    (240, "v2", "needs_evidence"),
    (None, "v1", "needs_evidence"),
])
def test_release_policy_agrees_across_report_dashboard_and_download(setup, p95, workload, status):
    client, engine, _, _, _ = setup
    target = "http://fixture.test"
    baseline_label = "<script>alert(1)</script>"
    with Session(engine) as session:
        for run_id, latency, version, release, day in [
            ("release-baseline", 224, "v1", baseline_label, 1),
            ("release-candidate", p95, workload, "candidate", 2),
        ]:
            payload = {
                "run_id": run_id, "plan_id": "plan", "target": target, "tool": "k6",
                "status": "finished", "execution": {"environment": "staging",
                    "workload_version": version, "release_label": release, "target_request_rate": 15},
                "snapshot": {"requests": 30, "rps": 15, "error_rate": 0,
                             "latency": {"samples": 30 if latency is not None else 0, "p95_ms": latency},
                             "per_endpoint": [{"name": "Checkout", "requests": 30, "p95_ms": latency}]},
                "samples": [{"t": 1, "rps": 15, "p95": latency, "err": 0}],
                "verdict": {"overall_passed": True, "checks": []},
                "narrative": {"headline": "Run completed", "summary": "Measured checkout."},
            }
            session.add(RunResultRow(id=run_id, plan_id="plan", created_at=datetime(2026, 11, day),
                                     target_base_url=target, verdict="pass", report_json=json.dumps(payload)))
        session.commit()

    path = "/api/runs/release-baseline/release-policy"
    policy = {"budgets": {"max_p95_ms": 300, "max_p95_regression_percent": 10, "min_rps": 15}}
    assert client.put(path, json=policy, headers={"Origin": "https://untrusted.test"}).status_code == 403
    assert client.put(path, json={"budgets": {}}).status_code == 422
    assert client.put(path, json={"budgets": {"max_p95_ms": "300"}}).status_code == 422
    assert client.put(path, json=policy).status_code == 200
    audit = client.get("/api/audit").json()["events"]
    assert any(event["action"] == "release.baseline_approved" and event["entity_id"] == "release-baseline"
               for event in audit)
    candidate = "/api/runs/release-candidate"
    report = client.get(candidate + "/saved-report").json()
    decision = report["release_readiness"]
    assert decision["status"] == status and report["verdict"]["overall_passed"] is True
    assert client.get(candidate + "/report").json()["release_readiness"] == decision
    overview = client.get("/api/reporting/runs", params={
        "include_overview": "true", "role": "engineer",
    }).json()["overview"]
    assert overview["release_readiness"]["status"] == status
    viewer = client.get("/api/reporting/runs?include_overview=true&role=viewer").json()
    assert viewer["overview"]["release_readiness"] is None
    download = client.get(candidate + "/report/download")
    assert download.headers["Cache-Control"] == "no-store"
    html = download.text
    assert "Content-Security-Policy" in html
    assert "Release readiness · " + status.replace("_", " ").capitalize() in html
    assert decision["reason"] in html
    assert baseline_label not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    if p95 and workload == "v1":
        assert decision["comparison"]["endpoints"][0]["name"] == "Checkout"
    if status == "blocked":
        explanation = "The run passed its k6 thresholds. The release is blocked."
        assert explanation in decision["explanation"]
        assert explanation in html
        assert "Measured checkout." not in html
        assert not decision["rules"][-1]["passed"]
        assert decision["rules"][0]["passed"]
        assert client.put(path, json={"budgets": {"max_p95_regression_percent": 20}}).status_code == 200
        assert client.get(candidate + "/saved-report").json()["release_readiness"]["status"] == "ready"


def test_local_k6_release_walkthrough(setup):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Event, Thread
    from time import monotonic, sleep

    from perfagent.runner.k6_binary import find_k6

    if not find_k6():
        pytest.skip("The release walkthrough requires an installed k6 binary.")

    client, _, _, _, model = setup
    calls = []
    webpage_hit = Event()

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            if self.path == "/":
                self.respond(200, b"<h1>Release fixture</h1>", "text/html")
                webpage_hit.set()
            elif self.path == "/api/account":
                authorized = self.headers.get("Authorization") == "Bearer fixture"
                self.respond(200 if authorized else 401, b'{"account_id":1}' if authorized else b'{}')
            elif self.path == "/orders/order-42":
                self.respond(200, b'{"id":"order-42"}')
            else:
                self.respond(404, b'{}')

        def do_POST(self):
            calls.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path != "/orders":
                self.respond(404, b'{}')
            else:
                self.respond(201, self.server.checkout_body)

        def respond(self, status, body, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    server.checkout_body = b'{"id":"order-42"}'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    active = set()

    def generate(steps, headers=None, *, stoppable=False):
        candidate = LoadModel.model_validate({
            **model.model_dump(),
            "target_base_url": f"http://127.0.0.1:{server.server_port}",
            "headers": headers or {},
            "scenarios": [{
                "name": "release walkthrough",
                "steps": steps,
                "think_time": {"min_seconds": 1 if stoppable else 0, "max_seconds": 1 if stoppable else 0},
            }],
            "load_profile": {
                "stages": [{"duration_seconds": 10 if stoppable else 5, "target_users": 1}],
                "executor_options": {"executor": "constant-vus"} if stoppable else {
                    "executor": "shared-iterations", "iterations": 1,
                },
                "graceful_stop_seconds": 0,
            },
            "thresholds": [
                {"metric": "p95_ms", "op": "<=", "value": 500},
                {"metric": "error_rate", "op": "<", "value": .05},
            ],
        })
        response = client.post("/api/plan/plan/generate", json={"tool": "k6", "load_model": candidate.model_dump()})
        assert response.status_code == 200, response.text
        return response.json()["script_id"]

    def verify(script_id):
        response = client.post("/api/preflight", json={"script_id": script_id})
        assert response.status_code == 200, response.text
        return response.json()

    def start(script_id, release):
        response = client.post(f"/api/scripts/{script_id}/run", json={"release_label": release})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        active.add(run_id)
        return run_id

    def finish(run_id, expected_status="finished"):
        deadline = monotonic() + 20
        while monotonic() < deadline:
            response = client.get(f"/api/runs/{run_id}")
            assert response.status_code == 200, response.text
            if response.json()["status"] == expected_status:
                break
            sleep(.05)
        else:
            pytest.fail(f"Run did not reach {expected_status}: {response.text}")
        active.remove(run_id)
        response = client.get(f"/api/runs/{run_id}/report")
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["status"] == expected_status
        saved = client.get(f"/api/runs/{run_id}/saved-report")
        assert saved.status_code == 200, saved.text
        assert saved.json()["snapshot"] == report["snapshot"]
        assert saved.json()["verdict"] == report["verdict"]
        html = client.get(f"/api/runs/{run_id}/report/download")
        assert html.status_code == 200 and "Performance Test Report" in html.text
        verdict_label = {True: "PASS", False: "FAIL", None: "INCONCLUSIVE"}[report["verdict"]["overall_passed"]]
        assert f">{verdict_label}</span>" in html.text
        return report

    try:
        webpage = {"name": "Open page", "path": "/", "assertions": [
            {"kind": "body_contains", "op": "contains", "value": "Release fixture"},
        ]}
        script = generate([webpage])
        assert verify(script)["all_ok"] is True
        report = finish(start(script, "webpage"))
        assert report["snapshot"]["requests"] == 1
        assert report["verdict"]["overall_passed"] is True

        account = {"name": "Read account", "path": "/api/account", "assertions": [
            {"kind": "json_path", "op": "exists", "path": "account_id"},
        ]}
        script = generate([account], {"Authorization": "Bearer fixture"})
        assert verify(script)["all_ok"] is True
        assert finish(start(script, "authenticated-api"))["verdict"]["overall_passed"] is True

        script = generate([account], {"Authorization": "Bearer invalid"})
        failed = verify(script)
        assert failed["all_ok"] is False
        assert failed["journeys"][0]["requests"][0]["status"] == 401
        report = finish(start(script, "failed-auth"))
        assert report["verdict"]["overall_passed"] is False
        assert any(check["metric"] == "error_rate" and check["passed"] is False
                   for check in report["verdict"]["checks"])

        journey = [
            {"name": "Create order", "method": "POST", "path": "/orders",
             "extract": [{"var": "order_id", "path": "id"}],
             "assertions": [{"kind": "json_path", "op": "exists", "path": "id"}]},
            {"name": "Read order", "path": "/orders/${order_id}"},
        ]
        script = generate(journey)
        server.checkout_body = b"not JSON"
        assert verify(script)["all_ok"] is False
        server.checkout_body = b'{"id":"order-42"}'
        calls.clear()
        assert verify(script)["all_ok"] is True
        assert calls == ["/orders", "/orders/order-42"]
        report = finish(start(script, "multi-step"))
        assert report["snapshot"]["requests"] == 2
        assert report["verdict"]["overall_passed"] is True

        script = generate([webpage], stoppable=True)
        webpage_hit.clear()
        run_id = start(script, "interrupted")
        assert webpage_hit.wait(8)
        assert client.post(f"/api/runs/{run_id}/stop").status_code == 200
        assert finish(run_id, "stopped")["verdict"]["overall_passed"] is None
        report = finish(start(script, "restarted"))
        assert report["execution"]["release_label"] == "restarted"
        assert report["verdict"]["overall_passed"] is True
    finally:
        for run_id in active:
            client.post(f"/api/runs/{run_id}/stop")
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
