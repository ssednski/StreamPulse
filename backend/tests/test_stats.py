import pytest

from tests.conftest import ev


def test_empty_database_returns_zeros(client):
    body = client.get("/v1/stats/summary").json()
    assert body["sessions"] == 0
    assert body["error_rate"] == 0
    assert body["p95_startup_ms"] == 0


def test_summary_kpis_match_hand_computed_values(client, seeded):
    body = client.get("/v1/stats/summary", params={"window_minutes": 60}).json()
    assert body["sessions"] == 4  # the 600-minute-old session is outside the window
    assert body["errors"] == 1
    assert body["error_rate"] == 0.25
    assert body["avg_startup_ms"] == 2500
    assert body["p95_startup_ms"] == 4000  # nearest-rank p95 of [1000, 2000, 3000, 4000]
    assert body["ad_requests"] == 4
    assert body["ad_impressions"] == 3
    assert body["ad_fill_rate"] == 0.75
    assert body["rebuffer_ratio"] == 0.1  # 2000 ms stalled / 20000 ms watched
    assert body["avg_bitrate_kbps"] == 3000


def test_wider_window_includes_older_events(client, seeded):
    body = client.get("/v1/stats/summary", params={"window_minutes": 1440}).json()
    assert body["sessions"] == 5
    assert body["errors"] == 2


def test_timeseries_is_zero_filled_and_consistent_with_summary(client, seeded):
    body = client.get(
        "/v1/stats/timeseries", params={"window_minutes": 60, "step_minutes": 5}
    ).json()
    points = body["points"]
    assert len(points) >= 12
    assert sum(p["sessions"] for p in points) == 4
    assert sum(p["errors"] for p in points) == 1
    assert any(p["sessions"] == 0 for p in points)  # gaps are present, not skipped
    timestamps = [p["ts"] for p in points]
    assert timestamps == sorted(timestamps)


def test_breakdown_by_device_and_cdn(client, seeded):
    by_device = client.get("/v1/stats/breakdown", params={"dimension": "device"}).json()
    rows = {r["key"]: r for r in by_device["rows"]}
    assert rows["tv"]["sessions"] == 4
    assert rows["mobile"]["sessions"] == 0  # mobile only has stall/end events in the seed
    assert by_device["rows"][0]["key"] == "tv"  # sorted by sessions, descending

    by_cdn = client.get("/v1/stats/breakdown", params={"dimension": "cdn"}).json()
    assert {r["key"] for r in by_cdn["rows"]} == {"akamai", "fastly"}


def test_breakdown_rejects_unknown_dimension(client):
    assert client.get("/v1/stats/breakdown", params={"dimension": "password"}).status_code == 422


def test_top_errors(client, post_events):
    post_events(
        ev("playback_error", error_code="CDN_5XX"),
        ev("playback_error", error_code="CDN_5XX"),
        ev("playback_error", error_code="DECODER_ERROR"),
    )
    body = client.get("/v1/stats/errors", params={"limit": 5}).json()
    assert body == [
        {"error_code": "CDN_5XX", "count": 2},
        {"error_code": "DECODER_ERROR", "count": 1},
    ]


def test_session_timeline_sorted_and_404(client, post_events):
    post_events(
        ev("session_end", 1, session_id="x"),
        ev("session_start", 5, session_id="x"),
        ev("playback_start", 4, session_id="x"),
    )
    types = [e["event_type"] for e in client.get("/v1/sessions/x").json()["events"]]
    assert types == ["session_start", "playback_start", "session_end"]
    assert client.get("/v1/sessions/nope").status_code == 404


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/v1/stats/summary", {"window_minutes": 0}),
        ("/v1/stats/summary", {"window_minutes": 10_081}),
        ("/v1/stats/timeseries", {"window_minutes": 10_080, "step_minutes": 1}),  # too many points
        ("/v1/stats/timeseries", {"window_minutes": 60, "step_minutes": 0}),
        ("/v1/stats/errors", {"limit": 0}),
    ],
)
def test_invalid_query_parameters_return_422(client, path, params):
    assert client.get(path, params=params).status_code == 422
