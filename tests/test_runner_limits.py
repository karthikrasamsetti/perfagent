from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest

from perfagent.config import Settings
from perfagent.runner import k6_runner


def _start():
    return k6_runner.start_run(
        run_id=uuid4().hex,
        script_id="fixture",
        tool="k6",
        target="http://fixture.test",
        content="import { sleep } from 'k6'; export default function () { sleep(60); }",
    )


def test_runner_reserves_capacity_until_the_worker_exits(monkeypatch):
    monkeypatch.setattr(k6_runner, "get_settings", lambda: Settings(perfagent_max_concurrent_runs=1))
    release = Event()

    def blocked_worker(run, content, max_seconds):
        assert release.wait(5)
        run.status = "finished"

    monkeypatch.setattr(k6_runner, "_run_worker", blocked_worker)
    first = _start()
    try:
        with pytest.raises(k6_runner.RunCapacityExceeded, match="slots are busy"):
            _start()
    finally:
        release.set()

    deadline = monotonic() + 5
    while monotonic() < deadline:
        with k6_runner._RUNS_LOCK:
            if first.run_id not in k6_runner._ACTIVE_RUNS:
                break
        sleep(0.01)
    assert first.status == "finished"
    assert first.run_id not in k6_runner._ACTIVE_RUNS


def test_wall_clock_limit_stops_an_idle_k6_script(monkeypatch):
    if k6_runner.find_k6() is None:
        pytest.skip("This test requires an installed k6.")
    monkeypatch.setattr(k6_runner, "get_settings", lambda: Settings(perfagent_max_run_seconds=1))
    run = _start()
    deadline = monotonic() + 10
    while run.status not in {"stopped", "error", "finished"} and monotonic() < deadline:
        sleep(0.02)
    try:
        assert run.status == "stopped", run.message
        assert "1-second execution limit" in run.message
        assert run.run_end_ts is not None
        assert run._proc is not None and run._proc.poll() is not None
    finally:
        k6_runner.stop_run(run.run_id)



def test_service_variables_are_excluded_from_k6_subprocesses(tmp_path, monkeypatch):
    from perfagent.runner.process_environment import k6_process_environment

    monkeypatch.setenv("OPENAI_API_KEY", "test-value")
    monkeypatch.setenv("K6_WEB_DASHBOARD", "true")
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/fixture.pem")
    env = k6_process_environment(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "K6_WEB_DASHBOARD" not in env
    assert env["SSL_CERT_FILE"] == "/etc/ssl/fixture.pem"
    assert env["HOME"] == env["TMPDIR"] == str(tmp_path)


@pytest.mark.parametrize("outcome", ["finished", "timeout", "stop"])
def test_managed_lifecycle_streams_summary_and_cleans_up(monkeypatch, outcome):
    import json
    import subprocess
    import sys
    from contextlib import contextmanager

    from perfagent.contracts.load_model import LoadModel
    from perfagent.generator import render
    from perfagent.runner.worker_protocol import WORKER_SUMMARY_TYPE

    model = LoadModel.model_validate({
        "target_base_url": "https://fixture.test",
        "scenarios": [{"name": "Browse", "steps": [{"name": "Products", "path": "/products"}]}],
        "load_profile": {"stages": [{"duration_seconds": 1, "target_users": 0}],
                         "arrival_rate": 1, "target_request_rate": 1, "pre_allocated_vus": 1,
                         "graceful_stop_seconds": 0},
    })
    expected = {"http_req_duration": {"thresholds": {"p(95)<500": True}}}
    summary = json.dumps({"type": WORKER_SUMMARY_TYPE, "metrics": expected})
    metric = json.dumps({"type": "Point", "metric": "http_reqs", "data": {"value": 1}})
    cleaned = Event()
    sockets = []

    @contextmanager
    def fake_docker(image, bridge, content, **limits):
        sockets.append(bridge)
        assert bridge.is_socket()
        body = f"print({metric!r}, flush=True); print({summary!r}, flush=True)"
        if outcome != "finished":
            body += "; import time; time.sleep(10)"
        with subprocess.Popen([sys.executable, "-c", body], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as proc:
            try:
                yield proc
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                cleaned.set()

    monkeypatch.setattr(k6_runner, "docker_worker", fake_docker)
    policy = k6_runner.ManagedWorkerOptions(
        image="sha256:" + "1" * 64, pinned_address="127.0.0.1",
        approved_origins=("https://fixture.test",), max_vus=1, max_rps=1, max_seconds=1,
    )
    run = k6_runner.start_run(
        uuid4().hex, "script", "k6", model.target_base_url, render(model)[1],
        model.model_dump_json(), metadata={"generated": True, "workload_version": "native"},
        managed=policy,
    )
    deadline = monotonic() + 5
    if outcome == "stop":
        while run.status != "running" and monotonic() < deadline:
            sleep(.01)
        assert k6_runner.stop_run(run.run_id)
    while run.run_id in k6_runner._ACTIVE_RUNS and monotonic() < deadline:
        sleep(.01)
    assert cleaned.is_set()
    assert sockets and not sockets[0].exists()
    assert run.status == ("finished" if outcome == "finished" else "stopped"), run.message
    assert run.metadata["workload_version"] != "native"
    if outcome == "finished":
        assert run.summary_metrics == expected
        assert run.snapshot["requests"] == 1
    if outcome == "timeout":
        assert "execution limit" in run.message
