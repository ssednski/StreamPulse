import random
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.models import PlaybackEvent
from app.schemas import EventIn
from simulator.__main__ import main, post_batch
from simulator.generator import Profile, build_session, iter_backfill, poisson

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


def serialise(event: dict) -> dict:
    return {**event, "ts": event["ts"].isoformat()}


def test_generated_events_satisfy_the_api_schema():
    rng = random.Random(1)
    for _ in range(300):
        for event in build_session(rng, NOW, Profile()):
            EventIn.model_validate(serialise(event))


def test_session_is_ordered_and_bookended():
    events = build_session(random.Random(2), NOW, Profile())
    assert events[0]["event_type"] == "session_start"
    assert events[-1]["event_type"] == "session_end"
    assert [e["ts"] for e in events] == sorted(e["ts"] for e in events)
    assert len({e["session_id"] for e in events}) == 1


def test_generation_is_deterministic_for_a_seed():
    a = build_session(random.Random(7), NOW, Profile())
    b = build_session(random.Random(7), NOW, Profile())
    assert a == b


def test_incident_degrades_the_affected_cdn_only():
    profile = Profile(incident_cdn="fastly", incident_start=NOW - timedelta(minutes=1))
    rng = random.Random(3)

    def stats(cdn: str) -> tuple[int, float]:
        errors, startups = 0, []
        for _ in range(3000):
            for e in build_session(rng, NOW, profile):
                if e["cdn"] != cdn:
                    continue
                errors += e["event_type"] == "playback_error"
                if e["event_type"] == "playback_start":
                    startups.append(e["value_ms"])
        return errors, sum(startups) / len(startups)

    fastly_errors, fastly_startup = stats("fastly")
    akamai_errors, akamai_startup = stats("akamai")
    assert fastly_errors > akamai_errors
    assert fastly_startup > 1.5 * akamai_startup


def test_backfill_never_emits_future_events():
    events = list(iter_backfill(random.Random(4), NOW, 10, 1.0, Profile()))
    assert events
    assert all(e["ts"] <= NOW for e in events)


def test_poisson_mean_is_close_to_lambda():
    rng = random.Random(5)
    draws = [poisson(rng, 4.0) for _ in range(5000)]
    assert 3.8 < sum(draws) / len(draws) < 4.2
    assert poisson(rng, 0) == 0


def test_post_batch_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503 if calls["n"] == 1 else 201, json={"accepted": 1})

    monkeypatch.setattr("simulator.__main__.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        post_batch(client, "http://api", [build_session(random.Random(1), NOW, Profile())[0]])
    assert calls["n"] == 2


def test_cli_backfill_end_to_end(monkeypatch, app, client):
    """Run the real CLI against the real app, routing HTTP through the test client."""
    app.state.settings.max_batch_size = 1000  # the fixture default is deliberately tiny
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        response = client.post(
            request.url.path,
            content=request.content,
            headers={"content-type": "application/json"},
        )
        return httpx.Response(response.status_code, content=response.content)

    monkeypatch.setattr(
        "simulator.__main__.httpx.Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    main(["--url", "http://api", "--seed", "1", "backfill", "--minutes", "5", "--rate", "1"])

    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlaybackEvent)) > 0
