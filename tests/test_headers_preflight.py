"""Tests for custom headers in the k6 renderer and the pre-flight checker."""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.generator.k6_renderer import render_k6
from perfagent.preflight import preflight


def _model(headers=None, port=8799):
    return LoadModel(
        target_base_url=f"http://127.0.0.1:{port}",
        scenarios=[Scenario(name="s", steps=[
            Step(name="list", method="GET", path="/products"),
            Step(name="login", method="POST", path="/login", body={"u": "demo"}),
        ])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
        headers=headers or {},
    )


# ---- headers in rendered script ----

def test_headers_rendered():
    s = render_k6(_model({"Authorization": "Bearer xyz"}))
    assert "const HEADERS =" in s
    assert "Bearer xyz" in s
    assert "headers: HEADERS" in s          # GET
    assert "Object.assign" in s             # POST merges content-type


def test_no_headers_backward_compatible():
    s = render_k6(_model())
    assert "const HEADERS" not in s


# ---- preflight ----

class _Handler(BaseHTTPRequestHandler):
    def _send(self, code):
        self.send_response(code); self.send_header("Content-Length", "2"); self.end_headers()
        self.wfile.write(b"{}")
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/products")
            self.end_headers()
            return
        self._send(200 if self.path == "/products" else 404)
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        if ln: self.rfile.read(ln)
        self._send(200 if self.path == "/login" else 404)
    def log_message(self, *a): pass


def _serve():
    """Start the stub target on a free port chosen by the OS.

    A fixed port made these tests flaky under `pytest -n auto`: two workers could run
    them at the same moment, share the port (Windows allows that), and one test would
    shut the server down while the other was still sending requests to it.
    """
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    return srv


def _stop(srv):
    srv.shutdown()
    srv.server_close()


def test_preflight_reports_status():
    srv = _serve()
    try:
        r = preflight(_model(port=srv.server_port))
        by = {x["path"]: x for x in r["results"]}
        assert by["/products"]["status"] == 200 and by["/products"]["ok"]
        assert by["/login"]["status"] == 200 and by["/login"]["ok"]
        assert r["all_ok"] is True
        assert r["ok"] == 2 and r["total"] == 2
    finally:
        _stop(srv)


def test_preflight_flags_bad_endpoint():
    srv = _serve()
    try:
        m = _model(port=srv.server_port)
        m.scenarios[0].steps.append(Step(name="missing", method="GET", path="/nope"))
        r = preflight(m)
        by = {x["path"]: x for x in r["results"]}
        assert by["/nope"]["status"] == 404 and not by["/nope"]["ok"]
        assert r["all_ok"] is False
    finally:
        _stop(srv)


def test_preflight_reports_redirect_without_following_it():
    server = _serve()
    try:
        model = _model(port=server.server_port)
        model.scenarios[0].steps = [Step(name="redirect", path="/redirect")]
        result = preflight(model)
        assert result["all_ok"] is False
        assert result["results"][0]["status"] == 302
        assert "use the final endpoint URL" in result["results"][0]["error"]
    finally:
        _stop(server)


def test_k6_verification_runs_every_journey_and_reports_failed_checks():
    import pytest

    from perfagent.contracts.load_model import Assertion, Extract
    from perfagent.runner.k6_binary import find_k6
    from perfagent.runner.validator import preflight_script

    if find_k6() is None:
        pytest.skip("An installed k6 binary is required.")
    server = _serve()
    try:
        model = _model(port=server.server_port)
        model.scenarios = [
            Scenario(name="Sign in", steps=[
                Step(name="Login", method="POST", path="/login", body={"u": "demo"},
                     extract=[Extract(var="session_id", path="session.id")],
                     assertions=[Assertion(kind="json_path", op="exists", path="session.id")]),
            ]),
            Scenario(name="Browse", steps=[Step(name="Browse products", path="/products")]),
        ]
        model.load_profile.start_users = 1
        for scenario in model.scenarios:
            scenario.think_time.min_seconds = scenario.think_time.max_seconds = 0

        result = preflight_script(render_k6(model))
        assert result["all_ok"] is False
        sign_in, browse = result["journeys"]
        assert sign_in["name"] == "sign_in"
        assert sign_in["requests"] == [{"method": "POST", "status": 200, "ok": True}]
        checks = {check["name"]: check["ok"] for check in sign_in["checks"]}
        assert checks["session.id exists"] is False
        assert checks["Login captured session_id"] is False
        assert browse["name"] == "browse" and browse["ok"] is True
    finally:
        _stop(server)
