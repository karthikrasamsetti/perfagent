"""Saved Git / Jenkins details: stored per plan after success, never secrets."""

from __future__ import annotations

import importlib
import json
import subprocess

import pytest

from tests.test_jenkins import FakeJenkins, USER, TOKEN as JENKINS_TOKEN

GIT_TOKEN = "ghp_SHOULD_NEVER_BE_STORED_123456"
SECRET = "Bearer sk-live-SUPERSECRET-123456"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    from tests.test_api import _make_engine, FakeProvider
    from perfagent.db import models as dbmodels
    from perfagent import config

    dbmodels._engine = None
    engine = _make_engine(f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.setattr(dbmodels, "get_engine", lambda *_a, **_k: engine)
    config.get_settings.cache_clear()
    monkeypatch.setenv("GIT_ALLOW_LOCAL", "true")
    from perfagent.api import app as appmod
    importlib.reload(appmod)
    monkeypatch.setattr(appmod, "build_provider", lambda *_a, **_k: FakeProvider())
    from fastapi.testclient import TestClient
    client = TestClient(appmod.app)
    client.engine = engine
    yield client
    config.get_settings.cache_clear()


@pytest.fixture()
def bare_repo(tmp_path):
    repo = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(repo)], check=True)
    return repo


@pytest.fixture()
def fake():
    f = FakeJenkins()
    yield f
    f.close()


def _plan_and_script(api, headers=None):
    from tests.test_api import _plan_body
    plan = api.post("/api/plan", json=_plan_body()).json()
    body = {"tool": "k6", **({"headers": headers} if headers else {})}
    gen = api.post(f"/api/plan/{plan['plan_id']}/generate", json=body).json()
    return plan["plan_id"], gen["script_id"]


def _all_db_text(engine) -> str:
    from sqlalchemy import text
    with engine.connect() as c:
        rows = c.execute(text("select git_json, jenkins_json from integration_settings")).fetchall()
    return json.dumps([list(r) for r in rows])


# ------------------------------------------------------------------ module

def test_save_get_defaults_and_forget(api):
    from perfagent import integrations as it
    p1, _ = _plan_and_script(api)
    p2, _ = _plan_and_script(api)
    it.save(p1, git={"repo_url": "https://github.com/o/r.git", "branch": "dev", "framework": "fw",
                     "test": "t1", "ci": ["github", "travis"], "token": GIT_TOKEN},
            jenkins={"url": "https://jenkins.corp", "username": "kb", "job": "fw-job",
                     "api_token": JENKINS_TOKEN, "environment": "uat"})
    g1 = it.get(p1)
    assert g1["git"] == {"repo_url": "https://github.com/o/r.git", "branch": "dev",
                         "framework": "fw", "test": "t1", "ci": ["github"]}
    assert g1["jenkins"] == {"url": "https://jenkins.corp", "username": "kb", "job": "fw-job",
                             "environment": "uat"}
    assert set(g1["saved"]) == {"git", "jenkins"}

    # a different plan only inherits the shared defaults, not framework/test/job
    g2 = it.get(p2)
    assert g2["git"] == {"repo_url": "https://github.com/o/r.git", "branch": "dev"}
    assert g2["jenkins"] == {"url": "https://jenkins.corp", "username": "kb", "environment": "uat"}
    assert g2["saved"] == []
    assert it.get(None)["jenkins"]["url"] == "https://jenkins.corp"

    assert GIT_TOKEN not in _all_db_text(api.engine) and JENKINS_TOKEN not in _all_db_text(api.engine)

    it.forget(p1, "jenkins")
    assert it.get(p1)["jenkins"] == {} and it.get(p2)["jenkins"] == {}
    assert it.get(p1)["git"]["framework"] == "fw"
    with pytest.raises(ValueError):
        it.forget(p1, "everything")


def test_urls_with_credentials_are_not_saved(api):
    from perfagent import integrations as it
    p, _ = _plan_and_script(api)
    it.save(p, git={"repo_url": f"https://x:{GIT_TOKEN}@github.com/o/r.git", "branch": "main"},
            jenkins={"url": "https://u:p@jenkins.corp", "username": "has space"})
    g = it.get(p)
    assert "repo_url" not in g["git"] and g["git"]["branch"] == "main"
    assert g["jenkins"] == {}
    assert GIT_TOKEN not in _all_db_text(api.engine)


def test_unknown_plan_only_updates_defaults(api):
    from perfagent import integrations as it
    it.save("doesnotexist", jenkins={"url": "https://j.corp", "job": "x"})
    assert it.get("doesnotexist")["saved"] == []
    assert it.get(None)["jenkins"] == {"url": "https://j.corp"}


# ------------------------------------------------------------------ saved by real actions

def test_push_saves_git_details_and_failure_does_not(api, bare_repo):
    pid, sid = _plan_and_script(api, {"Authorization": SECRET})
    bad = api.post(f"/api/scripts/{sid}/export/git",
                   json={"framework_name": "fw", "test_name": "t", "repo_url": "https://127.0.0.1:9/o/r.git",
                         "git_token": GIT_TOKEN})
    assert bad.status_code == 502
    assert api.get(f"/api/integrations?plan_id={pid}").json()["saved"] == []

    ok = api.post(f"/api/scripts/{sid}/export/git",
                  json={"framework_name": "Shop Perf", "test_name": "Browse", "branch": "main",
                        "repo_url": f"file://{bare_repo}", "ci": ["github", "jenkins"]})
    assert ok.status_code == 200, ok.text
    g = api.get(f"/api/integrations?plan_id={pid}").json()
    assert g["git"] == {"repo_url": f"file://{bare_repo}", "branch": "main", "framework": "shop-perf",
                        "test": "browse", "ci": ["github", "jenkins"]}
    assert g["saved"] == ["git"]
    assert GIT_TOKEN not in _all_db_text(api.engine) and SECRET not in _all_db_text(api.engine)


def test_jenkins_trigger_and_setup_save_details(api, fake):
    pid, _ = _plan_and_script(api)
    auth = {"jenkins_url": fake.url, "username": USER, "api_token": JENKINS_TOKEN, "plan_id": pid}
    r = api.post("/api/jenkins/setup-job", json={**auth, "job": "team-perf", "framework": "demo-perf",
                                                  "repo_url": "https://github.com/org/demo.git",
                                                  "branch": "develop", "git_credentials_id": "github-pat"})
    assert r.status_code == 200
    r = api.post("/api/jenkins/trigger", json={**auth, "job": "team-perf", "test": "checkout-peak",
                                                "environment": "uat"})
    assert r.status_code == 200
    j = api.get(f"/api/integrations?plan_id={pid}").json()["jenkins"]
    assert j == {"url": fake.url, "username": USER, "job": "team-perf", "test": "checkout-peak",
                 "environment": "uat", "repo_url": "https://github.com/org/demo.git",
                 "branch": "develop", "framework": "demo-perf", "git_credentials_id": "github-pat"}
    assert JENKINS_TOKEN not in _all_db_text(api.engine)

    # wrong token: nothing new is remembered
    other, _ = _plan_and_script(api)
    api.post("/api/jenkins/trigger", json={**auth, "plan_id": other, "api_token": "wrong-token",
                                            "job": "team-perf"})
    assert api.get(f"/api/integrations?plan_id={other}").json()["saved"] == []


def test_import_saves_git_details(api, bare_repo):
    from perfagent.gitexport import GitTarget, build_framework, publish
    from tests.test_git_import import _model
    target = GitTarget(repo_url=f"file://{bare_repo}", allow_local=True)
    publish(target, lambda r: build_framework(r, framework_name="shop-perf", test_name="health",
                                              model=_model(headers={}), plan_id="a" * 32,
                                              script_id="b" * 32).files, "seed")
    r = api.post("/api/git/import", json={"repo_url": f"file://{bare_repo}", "branch": "main",
                                           "framework_path": "shop-perf", "test": "health"})
    assert r.status_code == 200, r.text
    g = api.get(f"/api/integrations?plan_id={r.json()['plan_id']}").json()
    assert g["git"] == {"repo_url": f"file://{bare_repo}", "branch": "main",
                        "framework": "shop-perf", "test": "health"}


def test_forget_api(api, bare_repo):
    pid, sid = _plan_and_script(api)
    api.post(f"/api/scripts/{sid}/export/git", json={"framework_name": "fw", "test_name": "t",
                                                      "repo_url": f"file://{bare_repo}"})
    r = api.delete(f"/api/integrations?plan_id={pid}&section=git")
    assert r.status_code == 200 and r.json()["git"] == {}
    assert api.delete(f"/api/integrations?plan_id={pid}&section=nope").status_code == 400
    assert any(e["action"] == "integrations.forgotten" for e in api.get("/api/audit").json()["events"])