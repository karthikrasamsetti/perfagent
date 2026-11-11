"""Import from Git: scanning, round-trip of PerfAgent tests, other scripts, safety."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from perfagent.contracts.load_model import (
    DataFile, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step, Threshold,
)
from perfagent.gitexport import ExportError, GitTarget, build_framework, publish
from perfagent.gitexport.importer import import_test, read_other_script, scan_repo
from perfagent.gitexport.publisher import cloned_repo

SECRET = "Bearer sk-live-SUPERSECRET-123456"


def _model(**kw) -> LoadModel:
    base = dict(
        target_base_url="https://api.example.com",
        scenarios=[Scenario(name="browse", weight=1.0,
                            steps=[Step(name="list", path="/products/${sku}")])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=30, target_users=10)]),
        thresholds=[Threshold(metric="p95_ms", op="<", value=800)],
        headers={"Authorization": SECRET, "Content-Type": "application/json"},
    )
    base.update(kw)
    return LoadModel(**base)


def _git(*args, cwd=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True).stdout


def _commit_files(remote: Path, files: dict[str, str], tmp: Path, symlinks: dict[str, str] | None = None):
    work = tmp / f"w{len(list(tmp.iterdir()))}"
    _git("clone", "-q", str(remote), str(work))
    for rel, content in files.items():
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    for rel, dest in (symlinks or {}).items():
        try:
            os.symlink(dest, work / rel)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation needs admin privileges on Windows")
    _git("add", "-A", cwd=work)
    _git("commit", "-qm", "manual", cwd=work)
    _git("push", "-q", "origin", "HEAD:main", cwd=work)


@pytest.fixture()
def repo(tmp_path):
    remote = tmp_path / "remote.git"
    _git("init", "--bare", "-q", "-b", "main", str(remote))
    target = GitTarget(repo_url=f"file://{remote}", allow_local=True)
    m1 = _model(data_file=DataFile(filename="skus.csv", fields=["sku"], row_count=2))
    publish(target, lambda r: build_framework(
        r, framework_name="shop-perf", test_name="browse", model=m1, plan_id="a" * 32,
        script_id="b" * 32, data_file=("skus.csv", "sku\nA1\nB2\n"), include_data=True).files, "one")
    m2 = _model(headers={"Content-Type": "application/json"})
    m2.scenarios[0].steps[0].path = "/health"
    publish(target, lambda r: build_framework(
        r, framework_name="shop-perf", test_name="health", model=m2, plan_id="c" * 32,
        script_id="d" * 32).files, "two")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    _commit_files(remote, {
        "legacy/k6/smoke.js": "import http from 'k6/http';\nexport default function(){ http.get('https://x'); }\n",
        "legacy/locust/locustfile.py": "from locust import HttpUser, task\n",
        "legacy/jmeter/plan.jmx": '<?xml version="1.0"?>\n<jmeterTestPlan version="1.2"></jmeterTestPlan>\n',
        "src/app.js": "console.log('not a load test')\n",
    }, scratch, symlinks={"legacy/k6/evil.js": "/etc/passwd"})
    return remote, target, scratch


def _scan(target):
    with cloned_repo(target) as (r, sha):
        return scan_repo(r, sha)


def test_scan_finds_frameworks_and_other_scripts(repo):
    _remote, target, _ = repo
    scan = _scan(target)
    assert len(scan.commit) == 40
    [fw] = scan.frameworks
    assert fw.name == "shop-perf" and fw.path == "shop-perf"
    tests = {t.test: t for t in fw.tests}
    assert set(tests) == {"browse", "health"}
    b = tests["browse"]
    assert b.required_secrets == ["PERF_HEADER_AUTHORIZATION"]
    assert b.data_file == "skus.csv" and b.data_committed
    assert b.peak_users == 10 and not b.edited_in_git and b.error is None
    assert tests["health"].required_secrets == []
    others = {(s.path, s.tool) for s in scan.other_scripts}
    assert others == {("legacy/k6/smoke.js", "k6"), ("legacy/locust/locustfile.py", "locust"),
                      ("legacy/jmeter/plan.jmx", "jmeter")}


def test_import_restores_secret_and_data(repo):
    _remote, target, _ = repo
    with cloned_repo(target) as (r, _sha):
        imp = import_test(r, "shop-perf", "browse", {"PERF_HEADER_AUTHORIZATION": SECRET})
    assert imp.model.headers == {"Authorization": SECRET, "Content-Type": "application/json"}
    assert imp.missing_secrets == []
    assert imp.data_file == ("skus.csv", "sku\nA1\nB2\n")
    assert imp.model.thresholds[0].value == 800


def test_import_without_secret_drops_header_and_warns(repo):
    _remote, target, _ = repo
    with cloned_repo(target) as (r, _sha):
        imp = import_test(r, "shop-perf", "browse", {})
    assert "Authorization" not in imp.model.headers
    assert imp.missing_secrets == ["PERF_HEADER_AUTHORIZATION"]
    assert any("PERF_HEADER_AUTHORIZATION" in w for w in imp.warnings)


def test_edited_script_is_detected(repo):
    remote, target, scratch = repo
    with cloned_repo(target) as (r, _sha):
        js = (r / "shop-perf/tests/health/loadtest.js").read_text()
    _commit_files(remote, {"shop-perf/tests/health/loadtest.js": js + "\n// tweak\n"}, scratch)
    tests = {t.test: t for t in _scan(target).frameworks[0].tests}
    assert tests["health"].edited_in_git and not tests["browse"].edited_in_git
    with cloned_repo(target) as (r, _sha):
        imp = import_test(r, "shop-perf", "health")
    assert imp.edited_in_git and any("edited directly in Git" in w for w in imp.warnings)


def test_invalid_plan_is_reported_not_fatal(repo):
    remote, target, scratch = repo
    _commit_files(remote, {"shop-perf/tests/health/plan.json": '{"target_base_url": 5}'}, scratch)
    tests = {t.test: t for t in _scan(target).frameworks[0].tests}
    assert tests["health"].error and "not a valid plan" in tests["health"].error
    assert tests["browse"].error is None
    with cloned_repo(target) as (r, _sha), pytest.raises(ExportError):
        import_test(r, "shop-perf", "health")


@pytest.mark.parametrize("path", ["../../etc/passwd", "/etc/passwd", "legacy/k6/evil.js",
                                  ".git/config", "src/app.js"])
def test_other_script_reading_is_confined(repo, path):
    _remote, target, _ = repo
    with cloned_repo(target) as (r, _sha), pytest.raises(ExportError):
        read_other_script(r, path)


def test_read_other_script(repo):
    _remote, target, _ = repo
    with cloned_repo(target) as (r, _sha):
        tool, content = read_other_script(r, "legacy/k6/smoke.js")
    assert tool == "k6" and "k6/http" in content


@pytest.mark.parametrize("fw,test", [("..", "browse"), ("shop-perf", "../x"), ("legacy", "smoke")])
def test_import_rejects_bad_targets(repo, fw, test):
    _remote, target, _ = repo
    with cloned_repo(target) as (r, _sha), pytest.raises(ExportError):
        import_test(r, fw, test)


def test_missing_branch(repo):
    _remote, target, _ = repo
    with pytest.raises(ExportError), cloned_repo(
            GitTarget(repo_url=target.repo_url, branch="nope", allow_local=True)):
        pass


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
    monkeypatch.setenv("GIT_ALLOW_LOCAL", "true")
    from perfagent.api import app as appmod
    importlib.reload(appmod)
    monkeypatch.setattr(appmod, "build_provider", lambda *_a, **_k: FakeProvider())
    from fastapi.testclient import TestClient
    yield TestClient(appmod.app)
    config.get_settings.cache_clear()


def test_api_scan_import_generate_roundtrip(api, repo):
    remote, _target, _ = repo
    src = {"repo_url": f"file://{remote}", "branch": "main"}
    scan = api.post("/api/git/scan", json=src)
    assert scan.status_code == 200, scan.text
    sj = scan.json()
    assert sj["frameworks"][0]["tests"][0]["test"] == "browse"
    assert len(sj["other_scripts"]) == 3

    r = api.post("/api/git/import", json={**src, "framework_path": "shop-perf", "test": "browse",
                                          "secrets": {"PERF_HEADER_AUTHORIZATION": SECRET},
                                          "expected_commit": sj["commit"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["data_file_id"] and j["data_fields"] == ["sku"] and j["warnings"] == []
    assert j["load_model"]["headers"]["Authorization"] == SECRET

    plan = api.get(f"/api/plans/{j['plan_id']}").json()
    assert plan["goal"].startswith("Imported from Git:")
    gen = api.post(f"/api/plan/{j['plan_id']}/generate",
                   json={"tool": "k6", "data_file_id": j["data_file_id"]})
    assert gen.status_code == 200 and SECRET in gen.json()["content"]

    # round trip: export the imported test back and nothing changes in Git
    exp = api.post(f"/api/scripts/{gen.json()['script_id']}/export/git",
                   json={**src, "framework_name": "shop-perf", "test_name": "browse",
                         "include_data": True, "data_file_id": j["data_file_id"]})
    assert exp.status_code == 200, exp.text
    changed = [f for f in exp.json()["files"] if f.endswith(("loadtest.js", "plan.json", "skus.csv"))]
    assert changed  # files were written...
    diff = _git("--git-dir", str(remote), "diff", "HEAD~1", "HEAD", "--stat")
    assert "loadtest.js" not in diff and "plan.json" not in diff   # ...but identical


def test_api_script_view(api, repo):
    remote, _t, _ = repo
    r = api.post("/api/git/script", json={"repo_url": f"file://{remote}",
                                           "path": "legacy/locust/locustfile.py"})
    assert r.status_code == 200 and r.json()["tool"] == "locust"
    r = api.post("/api/git/script", json={"repo_url": f"file://{remote}", "path": "../../etc/passwd"})
    assert r.status_code == 400


def test_api_errors(api, repo):
    assert api.post("/api/git/scan", json={}).status_code == 400
    r = api.post("/api/git/scan", json={"repo_url": "https://127.0.0.1:9/o/r.git",
                                         "git_token": "ghp_TOKEN_SHOULD_NOT_LEAK_1234"})
    assert r.status_code == 502 and "ghp_TOKEN_SHOULD_NOT_LEAK_1234" not in r.text
    remote, _t, _ = repo
    r = api.post("/api/git/import", json={"repo_url": f"file://{remote}", "framework_path": "shop-perf",
                                           "test": "browse", "secrets": {"X": 5},
                                           "git_token": "ghp_TOKEN_SHOULD_NOT_LEAK_1234"})
    assert "ghp_TOKEN_SHOULD_NOT_LEAK_1234" not in r.text


def test_api_import_is_audited(api, repo):
    remote, _t, _ = repo
    api.post("/api/git/import", json={"repo_url": f"file://{remote}", "framework_path": "shop-perf",
                                       "test": "health"})
    events = api.get("/api/audit").json()["events"]
    assert any(e["action"] == "git.imported" and "shop-perf/tests/health" in e["summary"] for e in events)