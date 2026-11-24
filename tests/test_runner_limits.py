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
