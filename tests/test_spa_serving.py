"""React static assets and history routes coexist with FastAPI and the fallback."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ui(tmp_path, monkeypatch):
    from perfagent.api import app as api
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<h1>Preserved workspace</h1>', encoding='utf-8')
    spa = web / 'spa'
    assets = spa / 'assets'
    assets.mkdir(parents=True)
    (spa / 'index.html').write_text('<div id="root"></div><script type="module" src="/assets/app.js"></script>', encoding='utf-8')
    (assets / 'app.js').write_text('console.log("React bundle");', encoding='utf-8')
    monkeypatch.setattr(api, '_WEB_DIR', web)
    monkeypatch.setattr(api, '_SPA_DIR', spa)
    static = next(route.app for route in api.app.routes if getattr(route, 'name', '') == 'spa-assets')
    monkeypatch.setattr(static, 'directory', str(assets))
    monkeypatch.setattr(static, 'all_directories', [str(assets)])
    monkeypatch.setattr(static, 'config_checked', False)
    return TestClient(api.app), spa


def test_spa_root_assets_and_deep_link_refresh(ui):
    client, _ = ui
    for route in ['/', '/projects', '/projects/a/dashboard', '/projects/a/tests/b', '/projects/a/runs/r', '/admin/overview']:
        response = client.get(route)
        assert response.status_code == 200
        assert '<div id="root">' in response.text
    script = client.get('/assets/app.js')
    assert script.status_code == 200 and 'React bundle' in script.text


def test_api_and_missing_assets_do_not_fall_back_to_html(ui):
    client, _ = ui
    assert client.get('/api/missing-endpoint').status_code == 404
    assert client.get('/api/missing-endpoint').json()['detail'].lower() == 'not found'
    assert client.post('/api/missing-endpoint', json={}).status_code == 404
    assert client.post('/api/tools', json={}).status_code == 405
    assert client.get('/assets').status_code == 404
    assert client.get('/assets/missing.js').status_code == 404
    assert client.get('/legacy/missing').status_code == 404


def test_previous_workspace_and_no_build_fallback(ui):
    client, spa = ui
    assert 'Preserved workspace' in client.get('/legacy').text
    (spa / 'index.html').unlink()
    assert 'Preserved workspace' in client.get('/').text
    assert client.get('/projects/a').status_code == 404
    (spa / 'assets' / 'app.js').unlink()
    (spa / 'assets').rmdir()
    assert client.get('/assets/app.js').status_code == 404
