from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest

from perfagent.api import access
from perfagent.config import Settings


@pytest.fixture
def protected_client(monkeypatch):
    settings = Settings(
        perfagent_access_mode="managed",
        perfagent_gateway_secret=SecretStr("fixture-" * 5),
        perfagent_workspace_members={"member"},
    )
    monkeypatch.setattr(access, "get_settings", lambda: settings)
    app = FastAPI()
    app.add_middleware(access.WorkspaceAccess)

    @app.get("/api/report")
    @app.post("/api/report")
    def report(request: Request):
        principal = getattr(request.state, "principal", None)
        return {"subject": principal.subject if principal else None,
                "gateway_secret_forwarded": "x-perfagent-gateway-secret" in request.headers}

    with TestClient(app) as client:
        yield client, settings


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_managed_workspace_rejects_direct_and_forged_identity(protected_client, method):
    client, _ = protected_client
    assert client.request(method, "/api/report").status_code == 401
    assert client.request(method, "/api/report", headers={
        "X-PerfAgent-Subject": "member", "X-PerfAgent-Assurance": "mfa",
    }).status_code == 401


def test_managed_workspace_requires_membership_and_mfa(protected_client):
    client, _ = protected_client
    headers = {"X-PerfAgent-Gateway-Secret": "fixture-" * 5}
    assert client.post("/api/report", headers={**headers, "X-PerfAgent-Subject": "member"}).status_code == 403
    assert client.post("/api/report", headers={
        **headers, "X-PerfAgent-Subject": "outsider", "X-PerfAgent-Assurance": "mfa",
    }).status_code == 403
    response = client.post("/api/report", headers={
        **headers, "X-PerfAgent-Subject": "member", "X-PerfAgent-Assurance": "mfa",
    })
    assert response.json() == {"subject": "member", "gateway_secret_forwarded": False}


def test_incomplete_managed_config_fails_closed(protected_client):
    client, settings = protected_client
    settings.perfagent_gateway_secret = SecretStr("")
    assert client.get("/api/report").status_code == 503


def test_local_workspace_keeps_existing_local_access(protected_client):
    client, settings = protected_client
    settings.perfagent_access_mode = "local"
    assert client.get("/api/report").status_code == 200


def test_real_app_applies_managed_access_before_routes(monkeypatch):
    from perfagent.api.app import app

    settings = Settings(
        perfagent_access_mode="managed",
        perfagent_gateway_secret=SecretStr("fixture-" * 5),
        perfagent_workspace_members={"member"},
    )
    monkeypatch.setattr(access, "get_settings", lambda: settings)
    with TestClient(app) as client:
        assert client.get("/api/tools").status_code == 401
        assert client.post("/api/preflight", json={}).status_code == 401
        assert client.put("/api/runs/any/release-policy", json={}).status_code == 401
        headers = {
            "X-PerfAgent-Gateway-Secret": "fixture-" * 5,
            "X-PerfAgent-Subject": "member",
            "X-PerfAgent-Assurance": "mfa",
        }
        response = client.get("/api/tools", headers=headers)
        assert response.status_code == 200
        assert "k6" in response.json()["tools"]
        available = client.get("/api/run/available", headers=headers).json()
        assert available == {"k6": False, "reason": access.MANAGED_EXECUTION_DETAIL}
        for path, body in [
            ("/api/preflight", {"script_id": "any"}),
            ("/api/preflight", {}),
            ("/api/scripts/any/validate", {}),
            ("/api/scripts/any/run", {}),
            ("/api/scripts/any/run", {"smoke": True}),
            ("/api/jenkins/trigger", {}),
        ]:
            denied = client.post(path, json=body, headers=headers)
            assert denied.status_code == 403, path
            assert denied.json()["detail"] == access.MANAGED_EXECUTION_DETAIL
