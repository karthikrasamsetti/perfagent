"""Request data: field sources, sample values, previews, and how data-file rows are used."""

from __future__ import annotations

import collections
import json
import random
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from perfagent import request_data as rd
from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import (
    DataFile,
    Extract,
    LoadModel,
    LoadProfileType,
    Scenario,
    Step,
    ThinkTime,
)
from perfagent.generator import generate_script, generators
from perfagent.planner.profile import build_profile

COLUMNS = ["username", "branch"]
ROWS = [{"username": f"user{i}", "branch": f"B{i % 3}"} for i in range(6)]
BODY = {
    "username": "${username}",
    "branch": "${branch}",
    "orderId": "${uuid}",
    "qty": "${randomInt(1,5)}",
    "serviceCode": "GRND",
    "weight": 3120,
    "ref": "ord-${sequential}",
    "auth": "${token}",
    "address": {"city": "${randomCity}", "lines": ["12 Main St", "${randomString(6)}"]},
}


def _model(row_mode="random", data=True, scenarios=1, body=None, extract=False):
    steps = [Step(name="order", method="POST", path="/orders/${branch}", body=body or BODY)]
    if extract:
        steps.insert(0, Step(name="login", method="POST", path="/login", body={"u": "demo"},
                             extract=[Extract(var="token", source="json", path="token")]))
    return LoadModel(
        target_base_url="http://127.0.0.1:8000",
        scenarios=[Scenario(name=f"journey {i}", steps=steps,
                            think_time=ThinkTime(min_seconds=0, max_seconds=0.05))
                   for i in range(scenarios)],
        load_profile=build_profile(LoadProfileType.RAMP, 4, 4),
        data_file=DataFile(filename="users.json", fields=COLUMNS, row_count=len(ROWS),
                           source_format="json", row_mode=row_mode) if data else None,
    )


# ------------------------------------------------------- generator samples ----

def test_every_generator_the_script_knows_has_a_sample_value():
    """A generator added to the k6 renderer must be previewable too."""
    tokens = list(generators._SIMPLE) + [
        "randomInt(1,100)", "randomString(8)", "randomFrom(a,b,c)", "dateOffset(3,'days')"]
    for token in tokens:
        assert generators.is_generator(token), token
        assert rd.sample_generator(token) is not None, token
    assert rd.sample_generator("username") is None            # a column, not a generator


def test_generator_samples_have_the_right_shape():
    rng = random.Random(7)
    assert len(rd.sample_generator("uuid", rng)) == 36
    assert rd.sample_generator("randomEmail", rng).endswith("@loadtest.test")
    assert 1 <= rd.sample_generator("randomInt(1,5)", rng) <= 5
    assert len(rd.sample_generator("randomString(12)", rng)) == 12
    assert rd.sample_generator("randomFrom(a,b,c)", rng) in ("a", "b", "c")
    assert rd.sample_generator("randomFrom(1,2,3)", rng) in (1, 2, 3)
    assert rd.sample_generator("dateOffset(3,'days')", rng).endswith("Z")
    assert rd.sample_generator("sequential", index=0) != rd.sample_generator("sequential", index=1)


# ------------------------------------------------------------- classifying ----

def test_each_field_gets_its_source():
    fields = {f["path"]: f for f in rd.describe_fields(BODY, COLUMNS)}
    assert fields["username"]["source"] == "file" and fields["username"]["token"] == "username"
    assert fields["orderId"]["source"] == "generated" and fields["orderId"]["token"] == "uuid"
    assert fields["qty"]["token"] == "randomInt(1,5)"
    assert fields["serviceCode"]["source"] == "fixed" and fields["weight"]["source"] == "fixed"
    assert fields["ref"]["source"] == "mixed"                  # text + a token
    assert fields["auth"]["source"] == "captured"              # not generated, not a column
    assert fields["address.city"]["source"] == "generated"
    assert fields["address.lines[0]"]["source"] == "fixed"
    assert fields["address.lines[1]"]["source"] == "generated"
    assert [f["path"] for f in rd.describe_fields(BODY, COLUMNS)][:3] == [
        "username", "branch", "orderId"]                       # body order is kept


def test_a_column_name_only_counts_when_the_file_has_it():
    assert rd.classify_value("${username}", [])["source"] == "captured"
    assert rd.classify_value("${username}", ["username"])["source"] == "file"
    assert rd.classify_value(5)["source"] == "fixed"


# ---------------------------------------------------------------- filling ----

def test_resolve_fills_file_and_generated_values_and_keeps_types():
    out = rd.resolve(BODY, ROWS[2], random.Random(1), index=4)
    assert out["username"] == "user2" and out["branch"] == "B2"
    assert len(out["orderId"]) == 36
    assert isinstance(out["qty"], int) and 1 <= out["qty"] <= 5     # a number stays a number
    assert out["serviceCode"] == "GRND" and out["weight"] == 3120
    assert out["ref"] == "ord-1000004"
    assert out["auth"] == "${token}"                       # only known during the run
    assert out["address"]["lines"][0] == "12 Main St" and len(out["address"]["lines"][1]) == 6
    assert rd.unresolved_tokens(out) == ["token"]
    assert BODY["username"] == "${username}"               # the plan itself is untouched


def test_resolve_without_a_row_leaves_columns_alone():
    out = rd.resolve({"u": "${username}", "id": "${uuid}"}, None)
    assert out["u"] == "${username}" and len(out["id"]) == 36


def test_preflight_sends_real_values_not_placeholder_text():
    from perfagent.preflight import _fill_body, _fill_placeholders
    body = _fill_body({"email": "${randomEmail}", "u": "${username}"}, {"username": "amy"})
    assert body["u"] == "amy" and "${" not in body["email"]
    assert _fill_placeholders("/orders/${branch}/${uuid}", {"branch": "B1"}).startswith("/orders/B1/")
    assert "${" not in _fill_placeholders("/orders/${branch}/${uuid}", {"branch": "B1"})


# ------------------------------------------------------------------- rows ----

def test_rows_are_handed_out_by_mode():
    assert rd.pick_rows(ROWS, 3, "sequential") == ROWS[:3]
    assert rd.pick_rows(ROWS[:2], 5, "sequential") == [ROWS[0], ROWS[1], ROWS[0], ROWS[1], ROWS[0]]
    assert rd.pick_rows(ROWS[:2], 5, "unique") == ROWS[:2]        # stops when rows run out
    assert all(r in ROWS for r in rd.pick_rows(ROWS, 4, "random", random.Random(3)))
    assert rd.pick_rows([], 2) == [None, None]


def test_row_mode_is_validated():
    with pytest.raises(ValueError):
        DataFile(filename="x.csv", fields=["a"], row_mode="sometimes")
    assert DataFile(filename="x.csv", fields=["a"]).row_mode == "random"   # old plans still load


# ---------------------------------------------------------------- preview ----

def test_preview_shows_the_requests_that_will_be_sent():
    p = rd.preview_requests(_model("sequential", extract=True), ROWS, samples=3, seed=1)
    assert p["row_mode"] == "sequential" and p["rows_available"] == 6
    login, order = p["steps"]
    assert login["dynamic"] is False and len(login["requests"]) == 1   # fixed: shown once
    assert order["dynamic"] is True and len(order["requests"]) == 3
    first = order["requests"][0]
    assert first["url"] == "http://127.0.0.1:8000/orders/B0" and first["row_number"] == 1
    assert first["body"]["username"] == "user0"
    ids = [r["body"]["orderId"] for r in order["requests"]]
    assert len(set(ids)) == 3                                   # generated values differ
    assert [r["body"]["username"] for r in order["requests"]] == ["user0", "user1", "user2"]
    assert order["run_time_values"] == ["token"] and order["undefined"] == []


def test_preview_flags_a_name_with_no_source():
    # ${token} is used but nothing captures it, and there is no data file either
    p = rd.preview_requests(_model(data=False), None, seed=1)
    step = p["steps"][0]
    assert set(step["undefined"]) == {"username", "branch", "token"}
    assert step["run_time_values"] == []
    assert p["rows_available"] == 0


# ---------------------------------------------------------- generated k6 ----

def _script(row_mode, scenarios=1):
    return generate_script(PlanArtifact(load_model=_model(row_mode, scenarios=scenarios,
                                                          extract=True)), tool="k6").content


def test_random_rows_script_is_unchanged():
    s = _script("random")
    assert "DATA[Math.floor(Math.random() * DATA.length)]" in s
    assert "k6/execution" not in s and "_rowIndex" not in s


def test_sequential_rows_script():
    s = _script("sequential")
    assert "import exec from 'k6/execution';" in s
    assert "DATA[exec.scenario.iterationInTest % DATA.length]" in s


def test_unique_rows_script_gives_each_journey_its_own_rows():
    s = _script("unique", scenarios=3)
    for i in range(3):
        assert f"exec.scenario.iterationInTest * 3 + {i};" in s
    assert s.count("exec.test.abort(") == 3 and "Data file exhausted" in s


def test_no_exec_import_when_the_file_is_not_used():
    m = _model("unique", body={"a": "fixed"})
    m.scenarios[0].steps[0].path = "/orders"
    s = generate_script(PlanArtifact(load_model=m), tool="k6").content
    assert "k6/execution" not in s and "DATA" not in s


def test_real_k6_uses_each_row_once_and_stops_when_rows_run_out(tmp_path):
    """End to end with the real engine: what the target receives, per row mode."""
    from perfagent.runner.k6_binary import find_k6
    if find_k6() is None:
        pytest.skip("k6 is not on this machine yet")

    seen: dict[str, list] = collections.defaultdict(list)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen[self.path.split("/")[1]].append(json.loads(self.rfile.read(n) or b"{}"))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rows = [{"username": f"user{i}", "branch": "B"} for i in range(30)]
    body = {"username": "${username}", "id": "${randomString(16)}"}    # no remote imports
    try:
        results = {}
        for mode in ("sequential", "unique"):
            seen.clear()
            m = _model(mode, scenarios=2, body=body)
            m.target_base_url = f"http://127.0.0.1:{srv.server_port}"
            m.data_file.row_count = len(rows)
            work = tmp_path / mode
            work.mkdir()
            (work / "loadtest.js").write_text(
                generate_script(PlanArtifact(load_model=m), tool="k6").content, encoding="utf-8")
            (work / "users.json").write_text(json.dumps(rows), encoding="utf-8")
            proc = subprocess.run([find_k6(), "run", "--quiet", "loadtest.js"], cwd=work,
                                  capture_output=True, text=True, timeout=120)
            users = [b["username"] for b in seen["orders"]]
            results[mode] = (proc.returncode, collections.Counter(users),
                             [b["id"] for b in seen["orders"]], proc.stderr)
    finally:
        srv.shutdown()
        srv.server_close()

    code, counts, ids, _ = results["sequential"]
    assert code == 0 and len(counts) == 30 and max(counts.values()) > 1   # rows repeat
    assert len(set(ids)) == len(ids)                                      # generated: unique

    code, counts, ids, stderr = results["unique"]
    assert code == 108 and "Data file exhausted" in stderr                # stopped itself
    assert max(counts.values()) == 1                                      # never reused
    assert len(set(ids)) == len(ids)


# --------------------------------------------------------------------- API ----

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    from perfagent.api import app as appmod
    from perfagent.db import models as dbmodels

    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    dbmodels.Base.metadata.create_all(eng)
    monkeypatch.setattr(dbmodels, "get_engine", lambda *a, **k: eng)
    yield TestClient(appmod.app)
    eng.dispose()


def _upload(client, name="users.csv", text="username,branch\namy,B1\nbob,B2\ncat,B3\ndan,B1\n"):
    r = client.post("/api/data", files={"file": (name, text, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def _plan_json(**kw):
    return _model(data=False, **kw).model_dump(mode="json")


def test_api_upload_returns_the_first_rows_and_file_can_be_described(client):
    up = _upload(client)
    assert up["fields"] == ["username", "branch"] and up["row_count"] == 4
    assert up["sample_rows"][0] == {"username": "amy", "branch": "B1"}
    assert len(up["sample_rows"]) == 3
    again = client.get(f"/api/data/{up['data_file_id']}").json()
    assert again["filename"] == "users.csv" and again["sample_rows"] == up["sample_rows"]
    assert client.get("/api/data/nope").status_code == 404


def test_api_load_profile_is_deterministic(client):
    body = {"type": "stress", "max_users": 40, "duration_seconds": 60}
    a = client.post("/api/load-profile", json=body).json()
    assert a == client.post("/api/load-profile", json=body).json()
    assert a["max_users"] == 40 and a["peak_users"] == 52          # stress goes past the target
    assert a["load_profile"]["type"] == "stress"
    ramp = client.post("/api/load-profile",
                       json={"type": "ramp", "max_users": 10, "duration_seconds": 20}).json()
    assert ramp["peak_users"] == 10 and ramp["total_seconds"] == 20
    assert client.post("/api/load-profile",
                       json={"type": "ramp", "max_users": 0, "duration_seconds": 20}
                       ).status_code == 422


def test_api_request_preview_uses_the_uploaded_file(client):
    up = _upload(client)
    r = client.post("/api/request-preview", json={
        "load_model": _plan_json(extract=True), "data_file_id": up["data_file_id"],
        "data_row_mode": "sequential", "samples": 2})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["row_mode"] == "sequential" and p["rows_available"] == 4
    order = p["steps"][1]
    assert [q["body"]["username"] for q in order["requests"]] == ["amy", "bob"]
    assert order["requests"][0]["url"].endswith("/orders/B1")
    assert order["undefined"] == [] and order["run_time_values"] == ["token"]


def test_api_request_preview_without_a_file_flags_missing_sources(client):
    p = client.post("/api/request-preview", json={"load_model": _plan_json()}).json()
    assert "username" in p["steps"][0]["undefined"]
    assert client.post("/api/request-preview", json={
        "load_model": _plan_json(), "data_file_id": "nope"}).status_code == 404
    assert client.post("/api/request-preview", json={
        "load_model": _plan_json(), "data_file_id": _upload(client)["data_file_id"],
        "data_row_mode": "sometimes"}).status_code == 400


def test_api_generate_applies_and_remembers_the_row_mode(client):
    from perfagent.db import PlanRow, get_session

    up = _upload(client)
    with get_session() as s:
        plan = PlanRow(target_base_url="http://127.0.0.1:8000",
                       load_model_json=json.dumps(_plan_json()))
        s.add(plan)
        s.commit()
        pid = plan.id

    g = client.post(f"/api/plan/{pid}/generate", json={
        "tool": "k6", "load_model": _plan_json(), "data_file_id": up["data_file_id"],
        "data_row_mode": "unique"})
    assert g.status_code == 200, g.text
    assert "exec.test.abort(" in g.json()["content"]
    saved = client.get(f"/api/plans/{pid}").json()["load_model"]["data_file"]
    assert saved["row_mode"] == "unique" and saved["filename"] == "users.csv"

    # regenerating without saying a mode keeps the one the plan has
    again = client.post(f"/api/plan/{pid}/generate", json={
        "tool": "k6", "data_file_id": up["data_file_id"]})
    assert "exec.test.abort(" in again.json()["content"]
    # and it can be changed on its own
    rnd = client.post(f"/api/plan/{pid}/generate", json={"tool": "k6", "data_row_mode": "random"})
    assert "Math.random() * DATA.length" in rnd.json()["content"]
    assert client.post(f"/api/plan/{pid}/generate", json={
        "tool": "k6", "data_row_mode": "sometimes"}).status_code == 400


def test_run_that_the_script_stops_itself_is_reported_clearly(tmp_path, monkeypatch):
    """k6 exit 108 (exec.test.abort) is a stopped run with a plain reason, not a crash."""
    import sys
    import uuid as _uuid

    from perfagent.runner import k6_runner

    fake = tmp_path / "fake_k6.py"
    fake.write_text(
        "import sys\n"
        "sys.stderr.write('level=error msg=\"test aborted: Data file exhausted: every one "
        "of its 5 rows has been used once.\"\\n')\n"
        "sys.exit(108)\n", encoding="utf-8")
    monkeypatch.setattr(k6_runner, "ensure_k6", lambda: sys.executable)
    monkeypatch.setattr(k6_runner, "find_k6", lambda: sys.executable)
    real_popen = subprocess.Popen

    def popen(cmd, **kw):
        return real_popen([sys.executable, str(fake)], **kw)
    monkeypatch.setattr(k6_runner.subprocess, "Popen", popen)

    rid = _uuid.uuid4().hex
    run = k6_runner.start_run(run_id=rid, script_id="s", tool="k6",
                              target="http://x", content="// script")
    import time
    end = time.time() + 15
    while time.time() < end and run.ended_at is None:
        time.sleep(0.05)
    assert run.status == "stopped"
    assert "ran out of rows" in run.message
    k6_runner._RUNS.pop(rid, None)
