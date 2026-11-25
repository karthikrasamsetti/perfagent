import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from perfagent.api import browser_security
from perfagent.config import Settings


@pytest.fixture
def client(monkeypatch):
    settings = Settings(perfagent_trusted_browser_origins=["https://trusted.example"])
    monkeypatch.setattr(browser_security, "get_settings", lambda: settings)
    app = FastAPI()
    app.add_middleware(browser_security.BrowserWriteProtection)

    @app.post("/api/action")
    def action():
        return {"accepted": True}

    @app.get("/api/action")
    def read():
        return {"accepted": True}

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("headers", [
    {"Origin": "https://outside.example"},
    {"Origin": "null"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    [("Origin", "http://testserver"), ("Origin", "https://outside.example")],
])
def test_browser_write_rejects_untrusted_request(client, headers):
    response = client.post("/api/action", headers=headers)
    assert response.status_code == 403
    assert "origin" in response.json()["detail"]


@pytest.mark.parametrize("headers", [
    {},
    {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    {"Origin": "https://trusted.example"},
    {"Sec-Fetch-Site": "same-origin"},
])
def test_browser_write_preserves_same_origin_proxy_and_cli_requests(client, headers):
    response = client.post("/api/action", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"accepted": True}


def test_origin_guard_does_not_enable_cors(client):
    response = client.get("/api/action", headers={"Origin": "https://outside.example"})
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers



def test_browser_security_headers_are_present_on_reads_and_rejected_writes(client):
    for response in (client.get("/api/action"),
                     client.post("/api/action", headers={"Origin": "https://untrusted.example"})):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "same-origin"
        assert response.headers["Cache-Control"] == "no-store"
