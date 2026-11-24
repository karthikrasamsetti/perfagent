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
