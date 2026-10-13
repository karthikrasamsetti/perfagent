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


def _model(headers=None):
    return LoadModel(
        target_base_url="http://127.0.0.1:8799",
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
        self._send(200 if self.path == "/products" else 404)
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        if ln: self.rfile.read(ln)
        self._send(200 if self.path == "/login" else 404)
    def log_message(self, *a): pass


def _serve():
    srv = ThreadingHTTPServer(("127.0.0.1", 8799), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    return srv


def test_preflight_reports_status():
    srv = _serve()
    try:
        r = preflight(_model())
        by = {x["path"]: x for x in r["results"]}
        assert by["/products"]["status"] == 200 and by["/products"]["ok"]
        assert by["/login"]["status"] == 200 and by["/login"]["ok"]
        assert r["all_ok"] is True
        assert r["ok"] == 2 and r["total"] == 2
    finally:
        srv.shutdown()


def test_preflight_flags_bad_endpoint():
    srv = _serve()
    try:
        m = _model()
        m.scenarios[0].steps.append(Step(name="missing", method="GET", path="/nope"))
        r = preflight(m)
        by = {x["path"]: x for x in r["results"]}
        assert by["/nope"]["status"] == 404 and not by["/nope"]["ok"]
        assert r["all_ok"] is False
    finally:
        srv.shutdown()
