from sqlalchemy import func, select

from app.models import PlaybackEvent
from tests.conftest import ev


def count_rows(app) -> int:
    with app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(PlaybackEvent))


def test_accepts_valid_batch(app, post_events):
    response = post_events(ev("session_start"), ev("playback_start"))
    assert response.status_code == 201
    assert response.json() == {"accepted": 2}
    assert count_rows(app) == 2


def test_rejects_empty_batch(post_events):
    assert post_events().status_code == 422


def test_rejects_unknown_event_type(post_events):
    assert post_events({**ev("session_start"), "event_type": "teleport"}).status_code == 422


def test_rejects_unknown_device(post_events):
    assert post_events(ev("session_start", device="fridge")).status_code == 422


def test_conditional_required_fields(post_events):
    bad = [
        ev("playback_start", value_ms=None),
        ev("playback_error", error_code=None),
        ev("ad_request", ad_id=None),
        ev("bitrate_change", bitrate_kbps=None),
    ]
    for event in bad:
        response = post_events(event)
        assert response.status_code == 422, event["event_type"]


def test_one_bad_event_rejects_whole_batch(app, post_events):
    response = post_events(ev("session_start"), ev("playback_start", value_ms=None))
    assert response.status_code == 422
    assert count_rows(app) == 0


def test_rejects_oversized_batch(post_events):
    response = post_events(*[ev("session_start")] * 51)
    assert response.status_code == 413


def test_api_key_enforced_when_configured(settings, app, post_events):
    app.state.settings.ingest_api_key = "s3cret"
    assert post_events(ev("session_start")).status_code == 401
    assert post_events(ev("session_start"), headers={"X-API-Key": "wrong"}).status_code == 401
    assert post_events(ev("session_start"), headers={"X-API-Key": "s3cret"}).status_code == 201


def test_timezone_offsets_normalised_to_utc(client, post_events):
    # 19:00+02:00 is 17:00 UTC, i.e. 60 minutes before the frozen clock (18:00 UTC).
    post_events(ev("session_start", session_id="tz", ts="2026-11-12T19:00:00+02:00"))
    body = client.get("/v1/sessions/tz").json()
    assert body["events"][0]["ts"].startswith("2026-11-12T17:00:00")


def test_naive_timestamps_are_treated_as_utc(client, post_events):
    post_events(ev("session_start", session_id="naive", ts="2026-11-12T17:30:00"))
    assert (
        client.get("/v1/sessions/naive").json()["events"][0]["ts"].startswith("2026-11-12T17:30:00")
    )
