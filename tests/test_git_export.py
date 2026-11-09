"""Git export: framework layout, secret handling, Git publishing, API routes."""

from __future__ import annotations

import json
import subprocess
import zipfile
import io

import pytest

from perfagent.contracts.load_model import (
    DataFile, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step, Threshold,
)
from perfagent.gitexport import ExportError, GitTarget, build_framework, publish, slugify
from perfagent.gitexport.framework import render_export_script

SECRET = "Bearer sk-live-SUPERSECRET-123456"


def _model(**kw) -> LoadModel:
    base = dict(
        target_base_url="https://api.example.com",
        scenarios=[Scenario(name="browse", weight=1.0, steps=[Step(name="list", path="/products")])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=30, target_users=10)]),
        thresholds=[Threshold(metric="p95_ms", op="<", value=800)],
        headers={"Authorization": SECRET, "Content-Type": "application/json"},
    )
    base.update(kw)
    return LoadModel(**base)


def _all_text(root):
    return "\n".join(p.read_text(errors="ignore") for p in root.rglob("*") if p.is_file())


# ------------------------------------------------------------------ names

@pytest.mark.parametrize("raw,slug", [
    ("Payments Perf Suite", "payments-perf-suite"),
    ("checkout_peak", "checkout_peak"),
    ("  Login--Load  ", "login-load"),
])
def test_slugify(raw, slug):
    assert slugify(raw) == slug


@pytest.mark.parametrize("bad", ["", "../..", "///", "...", "-"])
def test_slugify_rejects_unusable(bad):
    with pytest.raises(ExportError):
        slugify(bad)


# ------------------------------------------------------------------ secrets

def test_secret_header_becomes_env_lookup_and_guard():
    script, secrets, sanitized = render_export_script(_model())
    assert SECRET not in script
    assert "(__ENV.PERF_HEADER_AUTHORIZATION || '')" in script
    assert "REQUIRED_SECRETS = ['PERF_HEADER_AUTHORIZATION']" in script
    assert '"Content-Type": "application/json"' in script     # non-secret kept as is
    assert secrets == {"PERF_HEADER_AUTHORIZATION": "Authorization"}
    assert SECRET not in sanitized.model_dump_json()


def test_correlated_header_is_not_treated_as_secret():
    m = _model(headers={"Authorization": "Bearer ${token}"})
    _script, secrets, _ = render_export_script(m)
    assert secrets == {}


def test_framework_layout_and_no_secret_anywhere(tmp_path):
    res = build_framework(tmp_path, framework_name="Payments Perf", test_name="Checkout Peak",
                          model=_model(), plan_id="p" * 32, script_id="s" * 32)
    fw = tmp_path / "payments-perf"
    for rel in ["README.md", "perfagent.json", "environments/dev.env", ".gitignore",
                "tests/checkout-peak/loadtest.js", "tests/checkout-peak/plan.json",
                "tests/checkout-peak/test.json", "scripts/run-tests.sh", "scripts/run-tests.ps1",
                "ci/Jenkinsfile", "ci/azure-pipelines.yml", "ci/gitlab-ci.yml"]:
        assert (fw / rel).is_file(), rel
    wf = tmp_path / ".github/workflows/perf-payments-perf.yml"
    assert "PERF_HEADER_AUTHORIZATION: ${{ secrets.PERF_HEADER_AUTHORIZATION }}" in wf.read_text()
    assert "credentialsId: 'PERF_HEADER_AUTHORIZATION'" in (fw / "ci/Jenkinsfile").read_text()
    assert SECRET not in _all_text(tmp_path)
    assert res.required_secrets == ["PERF_HEADER_AUTHORIZATION"]
    assert "BASE_URL=https://api.example.com" in (fw / "environments/dev.env").read_text()


def test_second_test_merges_and_keeps_user_files(tmp_path):
    build_framework(tmp_path, framework_name="fw", test_name="one", model=_model(),
                    plan_id="a" * 32, script_id="b" * 32)
    env = tmp_path / "fw/environments/dev.env"
    env.write_text("BASE_URL=https://dev.internal\n")          # user edits it
    m2 = _model(headers={"X-API-Key": "abcdef123456"})
    res = build_framework(tmp_path, framework_name="fw", test_name="two", model=m2,
                          plan_id="c" * 32, script_id="d" * 32)
    assert env.read_text() == "BASE_URL=https://dev.internal\n"  # not overwritten
    manifest = json.loads((tmp_path / "fw/perfagent.json").read_text())
    assert set(manifest["tests"]) == {"one", "two"}
    wf = (tmp_path / ".github/workflows/perf-fw.yml").read_text()
    assert "PERF_HEADER_AUTHORIZATION" in wf and "PERF_HEADER_X_API_KEY" in wf
    assert any("dev.env sets BASE_URL" in w for w in res.warnings)


def test_data_file_excluded_by_default(tmp_path):
    m = _model(data_file=DataFile(filename="users.csv", fields=["user"], row_count=2))
    data = ("users.csv", "user\nalice-customer-0001\nbob-customer-00002\n")
    res = build_framework(tmp_path, framework_name="fw", test_name="t", model=m,
                          plan_id="a" * 32, script_id="b" * 32, data_file=data)
    tdir = tmp_path / "fw/tests/t"
    assert not (tdir / "users.csv").exists()
    assert "users.csv" in (tdir / ".gitignore").read_text()
    assert "alice-customer-0001" not in _all_text(tmp_path)
    assert any("NOT committed" in w for w in res.warnings)


def test_data_file_committed_when_asked(tmp_path):
    m = _model(data_file=DataFile(filename="users.csv", fields=["user"], row_count=1))
    build_framework(tmp_path, framework_name="fw", test_name="t", model=m, plan_id="a" * 32,
                    script_id="b" * 32, data_file=("users.csv", "user\nu1\n"), include_data=True)
    assert (tmp_path / "fw/tests/t/users.csv").read_text() == "user\nu1\n"


def test_unknown_ci_rejected(tmp_path):
    with pytest.raises(ExportError):
        build_framework(tmp_path, framework_name="fw", test_name="t", model=_model(),
                        plan_id="a" * 32, script_id="b" * 32, ci=["travis"])


def test_run_script_is_valid_posix_sh(tmp_path):
    build_framework(tmp_path, framework_name="fw", test_name="t", model=_model(),
                    plan_id="a" * 32, script_id="b" * 32)
    rc = subprocess.run(["sh", "-n", str(tmp_path / "fw/scripts/run-tests.sh")]).returncode
    assert rc == 0


# ------------------------------------------------------------------ git

@pytest.fixture()
def bare_repo(tmp_path):
    repo = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(repo)], check=True)
    return repo


def _target(repo, branch="main"):
    return GitTarget(repo_url=f"file://{repo}", branch=branch, allow_local=True)


def _builder(name, model):
    return lambda root: build_framework(root, framework_name="fw", test_name=name, model=model,
                                        plan_id="a" * 32, script_id="b" * 32).files


def _remote_files(repo, branch="main"):
    out = subprocess.run(["git", "--git-dir", str(repo), "ls-tree", "-r", "--name-only", branch],
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


def test_publish_to_empty_repo_then_update(bare_repo):
    r1 = publish(_target(bare_repo), _builder("one", _model()), "first")
    assert r1.changed and r1.commit
    assert "fw/tests/one/loadtest.js" in _remote_files(bare_repo)

    r2 = publish(_target(bare_repo), _builder("one", _model()), "same again")
    assert not r2.changed and r2.commit is None          # no empty commits

    r3 = publish(_target(bare_repo), _builder("two", _model()), "second test")
    files = _remote_files(bare_repo)
    assert r3.changed and {"fw/tests/one/test.json", "fw/tests/two/test.json"} <= files
    blob = subprocess.run(["git", "--git-dir", str(bare_repo), "log", "-p", "main"],
                          capture_output=True, text=True).stdout
    assert SECRET not in blob


def test_publish_new_branch(bare_repo):
    publish(_target(bare_repo), _builder("one", _model()), "base")
    r = publish(_target(bare_repo, "perf/new-test"), _builder("two", _model()), "branch")
    assert r.changed
    assert "fw/tests/two/loadtest.js" in _remote_files(bare_repo, "perf/new-test")
    assert "fw/tests/two/loadtest.js" not in _remote_files(bare_repo, "main")


@pytest.mark.parametrize("url", [
    "https://user:pat@github.com/org/repo.git",   # token in URL
    "http://github.com/org/repo.git",             # plain http
    "/etc",                                       # local path without allow_local
    "ext::sh -c touch% /tmp/pwned",               # git remote helper trick
])
def test_bad_repo_urls_rejected(url):
    with pytest.raises(ExportError):
        publish(GitTarget(repo_url=url), lambda r: ["x"], "m")


def test_host_allow_list():
    t = GitTarget(repo_url="https://evil.example/org/repo.git", allowed_hosts=["github.com"])
    with pytest.raises(ExportError):
        publish(t, lambda r: ["x"], "m")


# ------------------------------------------------------------------ API

@pytest.fixture()
def api(tmp_path, monkeypatch, bare_repo):
    from tests.test_api import _make_engine, FakeProvider  # reuse fixtures' helpers
    import importlib
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


def _script(client, headers=None):
    from tests.test_api import _plan_body
    plan = client.post("/api/plan", json=_plan_body()).json()
    body = {"tool": "k6"}
    if headers:
        body["headers"] = headers
    return client.post(f"/api/plan/{plan['plan_id']}/generate", json=body).json()["script_id"]


def test_api_export_git(api, bare_repo):
    sid = _script(api, {"Authorization": SECRET})
    r = api.post(f"/api/scripts/{sid}/export/git",
                 json={"framework_name": "Shop Perf", "test_name": "Browse",
                       "repo_url": f"file://{bare_repo}", "branch": "main"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["changed"] and j["framework"] == "shop-perf" and j["test"] == "browse"
    assert j["required_secrets"] == ["PERF_HEADER_AUTHORIZATION"]
    assert "shop-perf/tests/browse/loadtest.js" in _remote_files(bare_repo)


def test_api_export_zip(api):
    sid = _script(api)
    r = api.post(f"/api/scripts/{sid}/export/zip",
                 json={"framework_name": "shop", "test_name": "browse", "ci": ["github"]})
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "shop/tests/browse/loadtest.js" in names
    assert ".github/workflows/perf-shop.yml" in names
    assert "shop/ci/Jenkinsfile" not in names


def test_api_export_rejects_stale_script(api):
    from tests.test_api import _plan_body
    plan = api.post("/api/plan", json=_plan_body()).json()
    pid = plan["plan_id"]
    sid = api.post(f"/api/plan/{pid}/generate", json={"tool": "k6"}).json()["script_id"]
    edited = plan["load_model"]
    edited["thresholds"] = [{"metric": "p95_ms", "op": "<", "value": 123}]
    api.post(f"/api/plan/{pid}/generate", json={"tool": "k6", "load_model": edited})
    r = api.post(f"/api/scripts/{sid}/export/zip", json={"framework_name": "a", "test_name": "b"})
    assert r.status_code == 409


def test_api_export_bad_name(api):
    sid = _script(api)
    r = api.post(f"/api/scripts/{sid}/export/git", json={"framework_name": "../..", "test_name": "x"})
    assert r.status_code == 400


def test_api_git_needs_repo_and_token(api):
    sid = _script(api)
    names = {"framework_name": "fw", "test_name": "t"}
    r = api.post(f"/api/scripts/{sid}/export/git", json=names)
    assert r.status_code == 400 and "repository URL" in r.json()["detail"]
    r = api.post(f"/api/scripts/{sid}/export/git",
                 json={**names, "repo_url": "https://github.com/org/repo.git"})
    assert r.status_code == 400 and "access token" in r.json()["detail"]


TOKEN = "ghp_THIS_IS_A_TEST_TOKEN_123456"


def test_api_token_never_echoed(api):
    sid = _script(api)
    # git fails (nothing listening): the error must not contain the token
    r = api.post(f"/api/scripts/{sid}/export/git",
                 json={"framework_name": "fw", "test_name": "t",
                       "repo_url": "https://127.0.0.1:9/org/repo.git", "git_token": TOKEN})
    assert r.status_code == 502 and TOKEN not in r.text
    # a type error in another field must not echo the token either
    r = api.post(f"/api/scripts/{sid}/export/git",
                 json={"framework_name": "fw", "test_name": "t", "include_data": "maybe",
                       "repo_url": "https://github.com/o/r.git", "git_token": TOKEN})
    assert r.status_code == 422 and TOKEN not in r.text


@pytest.mark.parametrize("url,user", [
    ("https://github.com/o/r.git", "x-access-token"),
    ("https://github.mycorp.com/o/r.git", "x-access-token"),
    ("https://gitlab.com/o/r.git", "oauth2"),
    ("https://gitlab.internal.bank/o/r.git", "oauth2"),
    ("https://bitbucket.org/o/r.git", "x-token-auth"),
    ("https://dev.azure.com/org/proj/_git/r", "perfagent"),
])
def test_username_derived_from_host(url, user):
    import base64
    from perfagent.gitexport.publisher import _git_env, token_username
    assert token_username(url) == user
    env = _git_env(GitTarget(repo_url=url, token="tok"))
    header = env["GIT_CONFIG_VALUE_0"].split()[-1]
    assert base64.b64decode(header).decode() == f"{user}:tok"


# ------------------------------------------------------------------ existing repositories

def test_refuses_existing_folder_not_created_by_perfagent(tmp_path):
    existing = tmp_path / "k6-scripts"
    existing.mkdir()
    (existing / "login.js").write_text("// hand-written")
    with pytest.raises(ExportError, match="not created by PerfAgent"):
        build_framework(tmp_path, framework_name="k6-scripts", test_name="t", model=_model(),
                        plan_id="a" * 32, script_id="b" * 32)
    assert (existing / "login.js").read_text() == "// hand-written"
    assert not (existing / "tests").exists()


def test_refuses_foreign_workflow_file(tmp_path):
    wf = tmp_path / ".github/workflows/perf-fw.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: someone else's pipeline\n")
    with pytest.raises(ExportError, match="not created by PerfAgent"):
        build_framework(tmp_path, framework_name="fw", test_name="t", model=_model(),
                        plan_id="a" * 32, script_id="b" * 32)
    assert wf.read_text() == "name: someone else's pipeline\n"


def test_existing_repo_files_untouched_by_push(bare_repo, tmp_path):
    work = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(bare_repo), str(work)], check=True)
    (work / "k6-scripts").mkdir()
    (work / "k6-scripts/login.js").write_text("import http from 'k6/http';\n")
    (work / "README.md").write_text("team readme\n")
    env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=work, check=True, env=env)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=work, check=True)

    publish(_target(bare_repo), _builder("one", _model()), "add perf test")
    files = _remote_files(bare_repo)
    assert {"k6-scripts/login.js", "README.md", "fw/tests/one/loadtest.js"} <= files
    readme = subprocess.run(["git", "--git-dir", str(bare_repo), "show", "main:README.md"],
                            capture_output=True, text=True).stdout
    assert readme == "team readme\n"
    with pytest.raises(ExportError, match="not created by PerfAgent"):
        publish(_target(bare_repo), lambda r: build_framework(
            r, framework_name="k6-scripts", test_name="x", model=_model(),
            plan_id="a" * 32, script_id="b" * 32).files, "should fail")


def test_api_uploaded_script_cannot_be_exported(api):
    up = api.post("/api/scripts/upload", json={"content": "import http from 'k6/http';\nexport default function(){}",
                                               "target_base_url": "http://x"}).json()
    r = api.post(f"/api/scripts/{up['script_id']}/export/zip",
                 json={"framework_name": "fw", "test_name": "t"})
    assert r.status_code == 400 and "uploaded scripts" in r.json()["detail"]


def test_api_push_is_audited(api, bare_repo):
    sid = _script(api, {"Authorization": SECRET})
    api.post(f"/api/scripts/{sid}/export/git",
             json={"framework_name": "fw", "test_name": "t", "repo_url": f"file://{bare_repo}"})
    events = api.get("/api/audit").json()["events"]
    pushed = [e for e in events if e["action"] == "git.pushed"]
    assert pushed and "fw/tests/t" in pushed[0]["summary"]
    assert SECRET not in str(events)