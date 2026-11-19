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
