"""Run in Jenkins: trigger, follow, results, stop and job set-up against a fake Jenkins."""

from __future__ import annotations

import base64
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from perfagent.ci import jenkins as jk

USER, TOKEN = "alice", "11aa22bb33cc44dd55ee"
SUMMARY = {
    "metrics": {
        "http_reqs": {"count": 1200, "rate": 40.0},
        "http_req_failed": {"value": 0.01, "passes": 12, "fails": 1188},
        "http_req_duration": {"avg": 120.0, "p(90)": 200.0, "p(95)": 250.0, "max": 900.0,
                              "thresholds": {"p(95)<800": False}},
        "errors": {"value": 0.01, "thresholds": {"rate<0.05": False}},
    }
}


class FakeJenkins:
    def __init__(self, *, require_crumb=False, parameterized=True, result="SUCCESS", summary=None):
        self.require_crumb = require_crumb
        self.jobs = {"demo-perf": {"parameterized": parameterized, "config": None},
                     "perf/inner": {"parameterized": True, "config": None}}
        self.result, self.summary = result, summary or SUMMARY
        self.triggered, self.queue_polls, self.build_polls = [], 0, 0
        self.stopped = False
        self.calls = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", headers=None, ctype="application/json"):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode()
                elif isinstance(body, str):
                    body = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authed(self):
                want = "Basic " + base64.b64encode(f"{USER}:{TOKEN}".encode()).decode()
                return self.headers.get("Authorization") == want

            def do_GET(self):
                fake.calls.append(("GET", self.path))
                if not self._authed():
                    return self._send(401, "unauthorized")
                return fake.handle(self, "GET", b"")

            def do_POST(self):
                fake.calls.append(("POST", self.path))
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if not self._authed():
                    return self._send(401, "unauthorized")
                if fake.require_crumb and self.headers.get("Jenkins-Crumb") != "crumb123":
                    return self._send(403, "No valid crumb was included in the request", ctype="text/html")
                return fake.handle(self, "POST", body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _job(self, path):
        m = re.match(r"^((?:/job/[^/]+)+)(/.*)?$", path)
        if not m:
            return None, path
        name = "/".join(re.findall(r"/job/([^/]+)", m.group(1)))
        from urllib.parse import unquote
        return unquote(name), m.group(2) or ""

    def handle(self, h, method, body):
        u = urlparse(h.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/crumbIssuer/api/json":
            return h._send(200, {"crumbRequestField": "Jenkins-Crumb", "crumb": "crumb123"})
        m = re.match(r"^/queue/item/(\d+)/api/json$", path)
        if m:
            self.queue_polls += 1
            if self.queue_polls == 1:
                return h._send(200, {"why": "Waiting for next available executor"})
            return h._send(200, {"executable": {"number": 12, "url": f"{self.url}/job/demo-perf/12/"}})
        if path == "/createItem" or path.endswith("/createItem"):
            parent, _ = self._job(path[: -len("/createItem")]) if path != "/createItem" else ("", "")
            name = q["name"][0]
            full = f"{parent}/{name}" if parent else name
            self.jobs[full] = {"parameterized": "<name>TEST</name>" in body.decode(), "config": body.decode()}
            return h._send(200, "")
        job, rest = self._job(path)
        if job is None:
            return h._send(404, "no")
        if job not in self.jobs:
            return h._send(404, "no such job")
        if rest == "/api/json":
            return h._send(200, {"name": job})
        if rest == "/config.xml" and method == "POST":
            self.jobs[job]["config"] = body.decode()
            return h._send(200, "")
        if rest == "/buildWithParameters" and method == "POST":
            if not self.jobs[job]["parameterized"]:
                return h._send(400, f"{job} is not parameterized", ctype="text/html")
            self.triggered.append({k: v[0] for k, v in parse_qs(body.decode()).items()})
            return h._send(201, "", {"Location": f"{self.url}/queue/item/7/"})
        m = re.match(r"^/(\d+)(/.*)$", rest)
        if m:
            sub = m.group(2)
            if sub == "/api/json" and "artifacts" in u.query:
                return h._send(200, {"artifacts": [
                    {"fileName": "checkout-peak-summary.json",
                     "relativePath": "demo-perf/results/checkout-peak-summary.json"},
                    {"fileName": "notes.txt", "relativePath": "demo-perf/results/notes.txt"}]})
            if sub == "/api/json":
                self.build_polls += 1
                building = self.build_polls < 2 and not self.stopped
                return h._send(200, {"building": building, "result": None if building else
                                     ("ABORTED" if self.stopped else self.result),
                                     "duration": 0 if building else 61000,
                                     "url": f"{self.url}/job/demo-perf/12/", "number": 12})
            if sub == "/logText/progressiveText":
                start = int(q.get("start", ["0"])[0])
                full = "Started by user alice\n=== checkout-peak ===\nPASS   checkout-peak\nFinished: SUCCESS\n"
                part = full[start:start + 30]
                more = start + len(part) < len(full)
                return h._send(200, part, {"X-Text-Size": str(start + len(part)),
                                           "X-More-Data": "true" if more else "false"}, ctype="text/plain")
            if sub == "/artifact/demo-perf/results/checkout-peak-summary.json":
                return h._send(200, self.summary)
            if sub == "/stop" and method == "POST":
                self.stopped = True
                return h._send(302, "", {"Location": f"{self.url}/job/demo-perf/12/"})
        return h._send(404, "not found")

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def fake():
    f = FakeJenkins()
    yield f
    f.close()


def _client(f, job="demo-perf", token=TOKEN):
    t = jk.JenkinsTarget(url=f.url, username=USER, api_token=token, job=job)
    jk.validate(t)
    return jk.JenkinsClient(t)


# ------------------------------------------------------------------ client

def test_trigger_queue_build_log_results(fake):
    c = _client(fake)
    qid = jk.trigger(c, {"TEST": "checkout-peak", "PERF_ENV": "uat"})
    assert qid == 7 and fake.triggered == [{"TEST": "checkout-peak", "PERF_ENV": "uat"}]
    assert jk.queue_status(c, qid).state == "queued"
    st = jk.queue_status(c, qid)
    assert st.state == "running" and st.number == 12
    assert jk.build_status(c, 12).state == "running"
    done = jk.build_status(c, 12)
    assert done.state == "finished" and done.result == "SUCCESS" and done.duration_ms == 61000
    log, start, more = "", 0, True
    while more:
        chunk, start, more = jk.console_chunk(c, 12, start)
        log += chunk
    assert "PASS   checkout-peak" in log and log.endswith("Finished: SUCCESS\n")
    [res] = jk.k6_results(c, 12)
    assert res["test"] == "checkout-peak" and res["verdict"] == "pass"
    assert res["requests"] == 1200 and res["p95_ms"] == 250.0 and res["error_rate"] == 0.01


def test_summary_threshold_true_means_failed():
    s = jk.summarize_k6({"metrics": {"http_req_duration": {"p(95)": 900, "thresholds": {"p(95)<800": True}}}})
    assert s["verdict"] == "fail" and s["thresholds"][0]["passed"] is False
    assert jk.summarize_k6({"metrics": {}})["verdict"] == "inconclusive"


def test_wrong_token(fake):
    with pytest.raises(jk.JenkinsError, match="rejected the user name or API token"):
        jk.trigger(_client(fake, token="nope-wrong-token"), {"TEST": "all", "PERF_ENV": "dev"})


def test_unknown_job(fake):
    with pytest.raises(jk.JenkinsError, match="not found"):
        jk.trigger(_client(fake, job="missing"), {"TEST": "all", "PERF_ENV": "dev"})


def test_not_parameterized_job_explains_first_build(fake):
    fake.jobs["demo-perf"]["parameterized"] = False
    with pytest.raises(jk.JenkinsError, match="first build"):
        jk.trigger(_client(fake), {"TEST": "all", "PERF_ENV": "dev"})


def test_crumb_is_fetched_when_required():
    f = FakeJenkins(require_crumb=True)
    try:
        assert jk.trigger(_client(f), {"TEST": "all", "PERF_ENV": "dev"}) == 7
        assert ("GET", "/crumbIssuer/api/json") in f.calls
    finally:
        f.close()


def test_job_in_folder(fake):
    jk.trigger(_client(fake, job="perf/inner"), {"TEST": "all", "PERF_ENV": "dev"})
    assert any(p.startswith("/job/perf/job/inner/buildWithParameters") for _m, p in fake.calls)


@pytest.mark.parametrize("params", [{"TEST": "all; rm -rf /", "PERF_ENV": "dev"},
                                    {"TEST": "all", "PERF_ENV": "../etc"[3:] + " x"}])
def test_bad_parameters_rejected(fake, params):
    with pytest.raises(jk.JenkinsError, match="invalid value"):
        jk.trigger(_client(fake), params)


@pytest.mark.parametrize("url,job,msg", [
    ("ftp://j", "a", "Jenkins URL"), ("https://u:p@j.example", "a", "API token"),
    ("https://j.example", "../../x", "job name"), ("https://j.example", "", "job name"),
])
def test_validation(url, job, msg):
    with pytest.raises(jk.JenkinsError, match=msg):
        jk.validate(jk.JenkinsTarget(url=url, username="u", api_token="t", job=job))


def test_allowed_hosts_and_http_warning():
    with pytest.raises(jk.JenkinsError, match="allowed"):
        jk.validate(jk.JenkinsTarget(url="https://evil.example", username="u", api_token="t",
                                     job="a", allowed_hosts=["jenkins.corp"]))
    w = jk.validate(jk.JenkinsTarget(url="http://jenkins.corp:8080", username="u", api_token="t", job="a"))
    assert w and "http" in w[0]


def test_unreachable_jenkins_hides_token():
    c = jk.JenkinsClient(jk.JenkinsTarget(url="http://127.0.0.1:9", username="u",
                                          api_token=TOKEN, job="a"))
    with pytest.raises(jk.JenkinsError) as e:
        jk.trigger(c, {"TEST": "all", "PERF_ENV": "dev"})
    assert TOKEN not in str(e.value) and "could not reach Jenkins" in str(e.value)


def test_setup_job_creates_then_updates(fake):
    c = _client(fake, job="new-perf")
    assert jk.setup_job(c, repo_url="https://github.com/org/demo.git", branch="main",
                        framework="demo-perf", git_credentials_id="github-pat") == "created"
    cfg = fake.jobs["new-perf"]["config"]
    assert "<scriptPath>demo-perf/ci/Jenkinsfile</scriptPath>" in cfg
    assert "<name>TEST</name>" in cfg and "<name>PERF_ENV</name>" in cfg
    assert "<credentialsId>github-pat</credentialsId>" in cfg and "*/main" in cfg
    # now parameterized: the very first trigger works without a manual build
    assert jk.trigger(c, {"TEST": "all", "PERF_ENV": "dev"}) == 7
    assert jk.setup_job(c, repo_url="https://github.com/org/demo.git", branch="develop",
                        framework="demo-perf") == "updated"
    assert "*/develop" in fake.jobs["new-perf"]["config"]


def test_setup_job_escapes_xml(fake):
    xml = jk.job_config_xml(repo_url="https://h/a.git", branch="main", script_path="x/ci/Jenkinsfile",
                            description="<script>&")
    assert "&lt;script&gt;&amp;" in xml


def test_stop(fake):
    c = _client(fake)
    jk.stop_build(c, 12)
    assert fake.stopped


# ------------------------------------------------------------------ API

@pytest.fixture()
def api(tmp_path, monkeypatch):
    import importlib
    from tests.test_api import _make_engine, FakeProvider
    from perfagent.db import models as dbmodels
    from perfagent import config

    dbmodels._engine = None
    url = f"sqlite:///{tmp_path/'t.db'}"
    monkeypatch.setattr(dbmodels, "get_engine", lambda *_a, **_k: _make_engine(url))
    config.get_settings.cache_clear()
    from perfagent.api import app as appmod
    importlib.reload(appmod)
    monkeypatch.setattr(appmod, "build_provider", lambda *_a, **_k: FakeProvider())
    from fastapi.testclient import TestClient
    yield TestClient(appmod.app)
    config.get_settings.cache_clear()


def _auth(f, **kw):
    return {"jenkins_url": f.url, "username": USER, "api_token": TOKEN, "job": "demo-perf", **kw}


def test_api_full_run(api, fake):
    r = api.post("/api/jenkins/trigger", json=_auth(fake, test="checkout-peak", environment="uat"))
    assert r.status_code == 200, r.text
    qid = r.json()["queue_id"]
    assert "http" in r.json()["warnings"][0]          # fake runs on plain http

    s = api.post("/api/jenkins/status", json=_auth(fake, queue_id=qid)).json()
    assert s["state"] == "queued" and "executor" in s["why"]
    s = api.post("/api/jenkins/status", json=_auth(fake, queue_id=qid)).json()
    assert s["state"] == "running" and s["build_number"] == 12 and s["log"]
    log, nxt = s["log"], s["log_next"]
    s = api.post("/api/jenkins/status", json=_auth(fake, build_number=12, log_start=nxt)).json()
    while s["log_more"] or s["state"] != "finished":
        log += s["log"]
        s = api.post("/api/jenkins/status", json=_auth(fake, build_number=12, log_start=s["log_next"])).json()
    log += s["log"]
    assert s["result"] == "SUCCESS" and s["verdict"] == "pass"
    assert s["results"][0]["p95_ms"] == 250.0 and "Finished: SUCCESS" in log

    actions = [e["action"] for e in api.get("/api/audit").json()["events"]]
    assert "jenkins.triggered" in actions and "jenkins.finished" in actions
    assert TOKEN not in json.dumps(api.get("/api/audit").json())


def test_api_failed_thresholds_give_fail_verdict(api):
    bad = json.loads(json.dumps(SUMMARY))
    bad["metrics"]["http_req_duration"]["thresholds"] = {"p(95)<800": True}
    f = FakeJenkins(result="FAILURE", summary=bad)
    try:
        qid = api.post("/api/jenkins/trigger", json=_auth(f)).json()["queue_id"]
        api.post("/api/jenkins/status", json=_auth(f, queue_id=qid))
        api.post("/api/jenkins/status", json=_auth(f, queue_id=qid))
        s = api.post("/api/jenkins/status", json=_auth(f, build_number=12)).json()
        while s["log_more"] or s["state"] != "finished":
            assert s["verdict"] is None and s["results"] is None   # only reported on the final poll
            s = api.post("/api/jenkins/status", json=_auth(f, build_number=12, log_start=s["log_next"])).json()
        assert s["result"] == "FAILURE" and s["verdict"] == "fail"
    finally:
        f.close()


def test_api_stop_and_setup(api, fake):
    assert api.post("/api/jenkins/stop", json=_auth(fake, build_number=12)).json() == {"stopped": True}
    r = api.post("/api/jenkins/setup-job", json=_auth(fake, job="team-perf", framework="demo-perf",
                                                       repo_url="https://github.com/org/demo.git"))
    assert r.status_code == 200 and r.json()["action"] == "created"
    r = api.post("/api/jenkins/setup-job", json=_auth(fake, job="team-perf", framework="Bad Name!",
                                                       repo_url="https://github.com/org/demo.git"))
    assert r.status_code == 400


def test_api_errors_never_echo_token(api, fake):
    r = api.post("/api/jenkins/trigger", json={})
    assert r.status_code == 400
    r = api.post("/api/jenkins/trigger", json=_auth(fake, job="missing"))
    assert r.status_code == 502 and TOKEN not in r.text
    r = api.post("/api/jenkins/status", json={**_auth(fake), "queue_id": "not-a-number"})
    assert r.status_code == 422 and TOKEN not in r.text


def test_console_annotations_are_stripped():
    import re as _re
    raw = ("Started by user \x1b[8mha:////4EB6msDg+AAAA=\x1b[0madmin\n"
           "\x1b[8mha:////4AmzYK==\x1b[0m[Pipeline] Start of Pipeline\n\x1b[32mgreen\x1b[0m done\n")
    cleaned = jk._ANSI.sub("", jk._CONSOLE_NOTE.sub("", raw))
    assert cleaned == "Started by user admin\n[Pipeline] Start of Pipeline\ngreen done\n"
    assert not _re.search("\x1b", cleaned)