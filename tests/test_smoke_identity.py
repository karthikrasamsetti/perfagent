"""Tester-facing workload identity and a real local-engine smoke regression."""
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.test_run_reliability import setup


def test_default_dashboard_and_all_roles_show_smoke_requests_and_identity(setup, monkeypatch):
    from tests.test_run_reliability import finished
    client, _, api, script_id, _ = setup
    run = finished(api, script_id, monkeypatch)
    run.metadata.update({"mode": "smoke", "test_name": "Product browsing",
                         "script_name": "products.smoke.js", "endpoint_summary": "GET /products"})
    assert client.get('/api/runs/original-run/report').status_code == 200
    for role in ('executive', 'qa_lead', 'engineer', 'viewer'):
        row = client.get('/api/reporting/runs?role='+role).json()['runs'][0]
        assert row['requests'] == 20
        assert row['test_name'] == 'Product browsing'
        assert row['script_name'] == 'products.smoke.js'
        assert row['mode'] == 'smoke'
    assert client.get('/api/reporting/runs?role=engineer&plan_id=other-test').json()['total'] == 0


def test_custom_test_and_script_names_are_frozen_and_safe(setup):
    client, _, _, _, model = setup
    model.test_name, model.script_filename = 'Checkout flow', 'checkout-flow.js'
    response = client.post('/api/plan/plan/generate', json={'tool': 'k6', 'load_model': model.model_dump()})
    assert response.status_code == 200, response.text
    assert response.json()['filename'] == 'checkout-flow.js'
    assert 'k6 run checkout-flow.js' in response.json()['content']
    readiness = client.get('/api/scripts/'+response.json()['script_id']+'/readiness').json()
    assert readiness['execution']['test_name'] == 'Checkout flow'
    assert readiness['execution']['endpoint_summary'] == 'GET /products'
    invalid = model.model_dump()
    invalid['script_filename'] = '../outside.js'
    assert client.post('/api/plan/plan/generate', json={'tool': 'k6', 'load_model': invalid}).status_code == 422


def test_uploaded_scripts_have_named_identity_without_fake_endpoints(setup, monkeypatch):
    from perfagent.runner.k6_runner import RunState
    client, _, api, _, _ = setup
    response = client.post('/api/scripts/upload', json={
        'test_name': 'Checkout from CI', 'filename': 'checkout.js',
        'target_base_url': 'http://fixture.test', 'content': 'export default function(){}'})
    assert response.status_code == 200, response.text
    script_id = response.json()['script_id']
    monkeypatch.setattr(api, 'start_run', lambda **kw: RunState(
        run_id=kw['run_id'], script_id=kw['script_id'], target=kw['target'], tool='k6'))
    assert client.post('/api/scripts/'+script_id+'/run').status_code == 200
    execution = client.get('/api/scripts/'+script_id+'/readiness').json()['execution']
    assert execution['test_name'] == 'Checkout from CI'
    assert execution['script_name'] == 'checkout.js'
    assert execution['endpoint_summary'] == 'Not recorded (uploaded script)'


def test_real_smoke_records_requests_from_local_target(setup):
    from perfagent.runner.k6_binary import find_k6
    if find_k6() is None:
        pytest.skip('Requires an installed k6; does not download one.')
    client, _, api, _, model = setup
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'{}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    run_id = None
    try:
        model.target_base_url = f'http://127.0.0.1:{server.server_port}'
        model.test_name, model.script_filename = 'Local products smoke', 'products.js'
        model.scenarios[0].think_time.min_seconds = 0.1
        model.scenarios[0].think_time.max_seconds = 0.1
        generated = client.post('/api/plan/plan/generate', json={'tool': 'k6', 'load_model': model.model_dump()})
        assert generated.status_code == 200, generated.text
        response = client.post('/api/scripts/'+generated.json()['script_id']+'/run', json={'smoke': True})
        assert response.status_code == 200, response.text
        run_id = response.json()['run_id']
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = client.get('/api/runs/'+run_id).json()
            if state['status'] in ('finished', 'stopped', 'error'):
                break
            time.sleep(0.25)
        assert state['status'] == 'finished', state
        assert received, 'The smoke test never sent a request to the local fixture.'
        assert state['snapshot']['requests'] > 0
        report = client.get('/api/runs/'+run_id+'/report')
        assert report.status_code == 200, report.text
        assert report.json()['snapshot']['requests'] == state['snapshot']['requests']
        row = client.get('/api/reporting/runs?role=executive').json()['runs'][0]
        assert row['requests'] == state['snapshot']['requests']
        assert row['test_name'] == 'Local products smoke'
        assert row['script_name'] == 'products.smoke.js'
    finally:
        if run_id:
            api.stop_run(run_id)
        server.shutdown()
        server.server_close()
