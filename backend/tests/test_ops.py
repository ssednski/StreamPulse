from prometheus_client.parser import text_string_to_metric_families

from app.metrics import LabelGuard
from tests.conftest import ev


def samples(client) -> list:
    text = client.get("/metrics").text
    return [s for family in text_string_to_metric_families(text) for s in family.samples]


def value(client, name: str, **labels) -> float:
    for s in samples(client):
        if s.name == name and all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    raise AssertionError(f"no sample {name} {labels}")


def test_health_and_readiness(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_business_metrics_are_recorded_on_ingest(client, post_events):
    post_events(
        ev("session_start", device="tv", cdn="akamai"),
        ev("playback_start", value_ms=1500),
        ev("buffer_end", value_ms=400),
        ev("ad_request"),
        ev("ad_impression"),
        ev("ad_error"),
        ev("playback_error", error_code="CDN_5XX", cdn="fastly"),
    )
    assert value(client, "streampulse_events_ingested_total", event_type="session_start") == 1
    assert value(client, "streampulse_sessions_started_total", device="tv", cdn="akamai") == 1
    assert value(client, "streampulse_playback_startup_seconds_sum") == 1.5
    assert value(client, "streampulse_rebuffer_seconds_count") == 1
    assert value(client, "streampulse_ad_requests_total", device="tv") == 1
    assert value(client, "streampulse_ad_impressions_total", device="tv") == 1
    assert value(client, "streampulse_ad_errors_total", device="tv") == 1
    errors = value(client, "streampulse_playback_errors_total", cdn="fastly", error_code="CDN_5XX")
    assert errors == 1


def test_rejected_events_do_not_touch_metrics(client, post_events):
    post_events(ev("playback_start", value_ms=None))
    assert not [s for s in samples(client) if s.name == "streampulse_events_ingested_total"]


def test_http_metrics_use_route_templates(client):
    client.get("/v1/sessions/abc-123")
    client.get("/v1/sessions/def-456")
    client.get("/definitely-not-a-route")
    assert (
        value(
            client,
            "streampulse_http_requests_total",
            path="/v1/sessions/{session_id}",
            status="404",
        )
        == 2
    )
    assert value(client, "streampulse_http_requests_total", path="unmatched", status="404") == 1


def test_label_guard_caps_cardinality():
    guard = LabelGuard(limit=2)
    assert [guard("a"), guard("b"), guard("c"), guard("a")] == ["a", "b", "other", "a"]
