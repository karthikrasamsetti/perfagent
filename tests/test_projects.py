"""Project scope, admin aggregation, migration and framework reuse."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from io import BytesIO
from zipfile import ZipFile

from pydantic import SecretStr
from sqlalchemy.orm import Session

from tests.test_run_reliability import setup
from perfagent.db.models import PlanRow, ProjectRow, RunResultRow


def project(client, name):
    response = client.post('/api/projects', json={
        'name': name, 'framework_name': name.lower(), 'repo_url': 'https://github.com/org/tests.git',
        'branch': 'performance', 'target_url': 'http://fixture.test', 'environment': 'staging'})
    assert response.status_code == 200, response.text
    return response.json()


def test_project_library_and_dashboard_are_scoped(setup):
    client, engine, _, _, _ = setup
    a, b = project(client, 'Commerce'), project(client, 'Payments')
    assert client.put('/api/plans/plan/project', json={'project_id': a['project_id']}).status_code == 200
    imported = client.post('/api/scripts/upload', json={'project_id': b['project_id'],
        'test_name': 'Pay invoice', 'filename': 'invoice.js', 'content': 'export default function(){}'})
    assert imported.status_code == 200
    with Session(engine) as s:
        s.add(RunResultRow(id='a-run', plan_id='plan', requests=50, verdict='pass'))
        s.add(RunResultRow(id='b-run', plan_id=imported.json()['plan_id'], requests=100, verdict='fail'))
        s.commit()
    library = client.get('/api/plans?project_id='+a['project_id']).json()['plans']
    assert [p['plan_id'] for p in library] == ['plan']
    assert client.get('/api/projects/'+a['project_id']+'/dashboard').json()['summary'] == {
        'tests': 1, 'runs': 1, 'requests': 50, 'pass_rate': 100.0}
    assert client.get('/api/reporting/runs?project_id='+b['project_id']).json()['total'] == 1
    assert client.get('/api/runs?project_id='+a['project_id']).json()['runs'][0]['run_id'] == 'a-run'
    assert client.put('/api/plans/plan/project', json={'project_id': b['project_id']}).status_code == 409


def test_names_are_case_insensitively_unique_within_their_scope(setup):
    client, _, _, _, _ = setup
    first, second = project(client, "Commerce"), project(client, "Payments")
    assert client.post("/api/projects", json={"name": " commerce "}).status_code == 409
    script = {"test_name": "Checkout", "filename": "checkout.js",
              "content": "export default function(){}"}
    assert client.post("/api/scripts/upload", json={**script, "project_id": first["project_id"]}).status_code == 200
    assert client.post("/api/scripts/upload", json={**script, "project_id": first["project_id"],
                                                    "test_name": " checkout "}).status_code == 409
    assert client.post("/api/scripts/upload", json={**script, "project_id": second["project_id"]}).status_code == 200
    assert client.put("/api/plans/plan/project", json={"project_id": first["project_id"],
                                                      "test_name": "Checkout"}).status_code == 409
    assert client.post("/api/scripts/upload", json={**script, "filename": "../checkout.js"}).status_code == 400


def test_admin_dashboard_requires_server_token(setup, monkeypatch):
    from perfagent.api import projects
    client, _, _, _, _ = setup
    project(client, 'Commerce')
    monkeypatch.setattr(projects, 'get_settings', lambda: SimpleNamespace(admin_api_token=SecretStr('test-only-key')))
    assert client.get('/api/admin/dashboard').status_code == 403
    assert client.get('/api/admin/dashboard?role=engineer').status_code == 403
    assert client.get('/api/admin/dashboard', headers={'X-Perfagent-Admin': 'wrong'}).status_code == 403
    response = client.get('/api/admin/dashboard', headers={'X-Perfagent-Admin': 'test-only-key'})
    assert response.status_code == 200
    assert response.json()['projects'][0]['name'] == 'Commerce'
    monkeypatch.setattr(projects, 'get_settings', lambda: SimpleNamespace(admin_api_token=SecretStr('')))
    assert client.get('/api/admin/dashboard', headers={'X-Perfagent-Admin': 'test-only-key'}).status_code == 403


def test_saved_workloads_do_not_mutate_test_or_script_snapshot(setup):
    client, engine, _, script_id, model = setup
    from perfagent.db.models import ScriptSnapshotRow
    with Session(engine) as s:
        before = s.get(ScriptSnapshotRow, script_id).load_model_json
    for name, users in [('Average', 20), ('Stress', 100)]:
        payload = {'name': name, 'load_profile': {'stages': [{'duration_seconds': 60, 'target_users': users}]},
                   'thresholds': [{'metric': 'p95_ms', 'op': '<', 'value': 500}]}
        assert client.post('/api/plans/plan/workloads', json=payload).status_code == 200
    workloads = client.get('/api/plans/plan/workloads').json()['workloads']
    assert len(workloads) == 2 and {w['name'] for w in workloads} == {'Average', 'Stress'}
    with Session(engine) as s:
        assert s.get(ScriptSnapshotRow, script_id).load_model_json == before
        assert json.loads(s.get(PlanRow, 'plan').load_model_json)['load_profile']['stages'][0]['target_users'] == 3


def test_project_defaults_drive_framework_zip(setup):
    client, _, _, script_id, _ = setup
    a = project(client, 'Commerce')
    client.put('/api/plans/plan/project', json={'project_id': a['project_id']})
    response = client.post('/api/scripts/'+script_id+'/export/zip', json={})
    assert response.status_code == 200, response.text
    with ZipFile(BytesIO(response.content)) as archive:
        assert any(name.endswith('commerce/tests/plan/loadtest.js') for name in archive.namelist())


def test_git_sync_updates_the_same_test_within_a_project(setup, monkeypatch, tmp_path):
    from perfagent.api import git_import_routes as routes
    client, _, _, _, model = setup
    a = project(client, 'Commerce')
    @contextmanager
    def clone(target):
        yield tmp_path, 'abcdef12'
    monkeypatch.setattr(routes, 'cloned_repo', clone)
    monkeypatch.setattr(routes, 'import_test', lambda *args: SimpleNamespace(
        model=model.model_copy(deep=True), warnings=[], framework='commerce', test='checkout',
        data_file=None, missing_secrets=[], edited_in_git=False))
    body = {'repo_url': 'https://github.com/org/tests.git', 'framework_path': 'commerce',
            'test': 'checkout', 'project_id': a['project_id']}
    first = client.post('/api/git/import', json=body)
    assert first.status_code == 200, first.text
    second = client.post('/api/git/import', json=body)
    assert second.status_code == 200, second.text
    assert first.json()['plan_id'] == second.json()['plan_id']
    assert len(client.get('/api/plans?project_id='+a['project_id']).json()['plans']) == 1


def test_migration_preserves_unassigned_tests(setup):
    _, engine, _, _, _ = setup
    from perfagent.db.migrate import prepare_database
    prepare_database(engine)
    with Session(engine) as s:
        assert s.get(PlanRow, 'plan').project_id == 'legacy'
        assert s.get(ProjectRow, 'legacy').name == 'Imported workspace'


def test_invalid_project_configuration_is_rejected(setup):
    client, _, _, _, _ = setup
    assert client.post('/api/projects', json={'name': '  '}).status_code == 422
    assert client.post('/api/projects', json={'name': 'Test', 'repo_url': 'https://user:secret@github.com/org/repo'}).status_code == 422


def test_managed_grants_scope_lists_and_direct_resource_access(setup, monkeypatch):
    from perfagent.api import access
    from perfagent.config import Settings

    client, engine, api, script_id, _ = setup
    allowed = project(client, "Commerce")["project_id"]
    denied = project(client, "Payments")["project_id"]
    assert client.put("/api/plans/plan/project", json={"project_id": allowed}).status_code == 200
    imported = client.post("/api/scripts/upload", json={
        "project_id": denied, "test_name": "Other test", "filename": "other.js",
        "content": "export default function(){}",
    })
    assert imported.status_code == 200, imported.text
    other_plan = imported.json()["plan_id"]
    with Session(engine) as session:
        session.add(RunResultRow(id="other-run", plan_id=other_plan))
        session.add(RunResultRow(id="visible-run", plan_id="plan", report_json='{"status":"finished"}'))
        session.commit()

    settings = Settings(
        perfagent_access_mode="managed",
        perfagent_gateway_secret=SecretStr("fixture-" * 5),
        perfagent_workspace_members={"viewer", "editor"},
        perfagent_project_grants={"viewer": {allowed: "viewer"}, "editor": {allowed: "editor"}},
    )
    monkeypatch.setattr(access, "get_settings", lambda: settings)

    def headers(subject):
        return {
            "X-PerfAgent-Gateway-Secret": "fixture-" * 5,
            "X-PerfAgent-Subject": subject,
            "X-PerfAgent-Assurance": "mfa",
        }

    viewer, editor = headers("viewer"), headers("editor")
    projects = client.get("/api/projects", headers=viewer).json()["projects"]
    assert [item["project_id"] for item in projects] == [allowed]
    assert client.get("/api/plans", headers=viewer).status_code == 403
    assert client.get("/api/plans", params={"project_id": allowed}, headers=viewer).status_code == 200
    assert client.get("/api/plans", params={"project_id": denied}, headers=editor).status_code == 404
    assert client.get("/api/plans/plan", headers=viewer).status_code == 404
    assert client.get("/api/plans/plan", headers=editor).status_code == 200
    assert client.get(f"/api/plans/{other_plan}", headers=editor).status_code == 404
    assert client.get(f"/api/scripts/{script_id}/download", headers=viewer).status_code == 404
    assert client.get(f"/api/scripts/{script_id}/download", headers=editor).status_code == 200
    assert client.get("/api/runs/other-run/saved-report", headers=editor).status_code == 404
    report = client.get("/api/runs/visible-run/saved-report", headers=viewer)
    assert report.json()["project_id"] == allowed
    assert client.put("/api/runs/visible-run/release-policy", headers=viewer,
                      json={"budgets": {"max_p95_ms": 100}}).status_code == 404
    assert client.get("/api/audit", headers=editor).status_code == 403
    settings.perfagent_managed_k6_image = "grafana/k6@sha256:" + "1" * 64
    calls = []

    def inspect_image(image, content, filename, data):
        calls.append((image, content))
        return {"ok": True, "status": "ok"}

    monkeypatch.setattr(api, "validate_isolated", inspect_image)
    validate_path = f"/api/scripts/{script_id}/validate"
    assert client.post(validate_path, headers=viewer).status_code == 404
    assert client.post(validate_path, headers=editor).json()["ok"] is True
    assert len(calls) == 1
    assert calls[0][0] == settings.perfagent_managed_k6_image
    assert client.post(f"/api/scripts/{script_id}/run", headers=editor).status_code == 403
