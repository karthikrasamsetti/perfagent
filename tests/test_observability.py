"""MetricsSink + /metrics rendering. Offline, no k6."""
from perfagent.observability.metrics import MetricsSink, render_latest


def _sink() -> MetricsSink:
    return MetricsSink(scenario="checkout", environment="prod",
                       load_tool="k6", run_id="r-1")


def test_record_request_increments_and_renders():
    s = _sink()
    s.mark_active(True)
    s.record_request(0.123, 200)
    s.record_request(0.456, 503)
    s.update_summary(rps=120.0, error_rate=0.5, active_vus=50)
    payload, content_type = render_latest()
    text = payload.decode()
    assert "perfagent_requests_total" in text
    assert 'status_class="2xx"' in text
    assert 'status_class="5xx"' in text
    assert "perfagent_rps" in text


def test_run_active_toggles():
    s = _sink()
    s.mark_active(True)
    s.mark_active(False)
    payload, _ = render_latest()
    assert "perfagent_run_active" in payload.decode()


def test_server_metrics_compare_two_minute_baseline_with_run(monkeypatch):
    import httpx

    from perfagent.config import Settings
    from perfagent.observability import correlation

    settings = Settings(perfagent_observability_target="https://fixture.test",
                        perfagent_prometheus_url="https://prometheus.test",
                        perfagent_prometheus_queries={"CPU (%)": "service_cpu"})
    monkeypatch.setattr(correlation, "get_settings", lambda: settings)

    def respond(request):
        assert request.url.path == "/api/v1/query_range"
        assert float(request.url.params["start"]) == 880
        assert float(request.url.params["end"]) == 1020
        assert request.url.params["query"] == "service_cpu"
        return httpx.Response(200, json={"data": {"result": [{"values": [
            [879, "100"], [880, "20"], [970, "30"], [1000, "40"],
            [1020, "50"], [1021, "100"],
        ]}]}})

    transport = httpx.MockTransport(respond)
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(correlation.httpx, "Client", lambda **kwargs: client)
    assert correlation.correlate("https://unrelated.test", 1000, 1020) is None
    result = correlation.correlate("https://fixture.test", 1000, 1020)
    assert result["metrics"] == [{"name": "CPU (%)", "baseline_mean": 25, "run_mean": 45}]
