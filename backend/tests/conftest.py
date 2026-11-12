import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


def ev(event_type: str, minutes_ago: float = 1, **overrides) -> dict:
    """Build an event payload dict relative to the frozen test clock."""
    event = {
        "session_id": "s1",
        "event_type": event_type,
        "ts": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "device": "tv",
        "cdn": "akamai",
        "content_id": "title-001",
        "content_type": "vod",
    }
    defaults = {
        "playback_start": {"value_ms": 1000},
        "buffer_end": {"value_ms": 500},
        "session_end": {"value_ms": 10_000},
        "bitrate_change": {"bitrate_kbps": 3000},
        "playback_error": {"error_code": "NETWORK_TIMEOUT"},
        "ad_request": {"ad_id": "ad-1"},
        "ad_impression": {"ad_id": "ad-1"},
        "ad_error": {"ad_id": "ad-1"},
    }
    return event | defaults.get(event_type, {}) | overrides


@pytest.fixture
def settings() -> Settings:
    # Set STREAMPULSE_TEST_DATABASE_URL to run the suite against PostgreSQL (CI does this).
    url = os.environ.get("STREAMPULSE_TEST_DATABASE_URL") or "sqlite://"
    return Settings(database_url=url, max_batch_size=50)


@pytest.fixture
def app(settings: Settings) -> Iterator:
    application = create_app(settings, clock=lambda: NOW)
    yield application
    Base.metadata.drop_all(application.state.engine)
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def post_events(client: TestClient):
    def _post(*events: dict, headers: dict | None = None):
        return client.post("/v1/events", json={"events": list(events)}, headers=headers or {})

    return _post


@pytest.fixture
def seeded(post_events):
    """Four sessions with hand-computed KPIs (see tests/test_stats.py)."""
    events = []
    for i, startup in enumerate([1000, 2000, 3000, 4000], start=1):
        sid = f"s{i}"
        events += [
            ev("session_start", 9, session_id=sid),
            ev("playback_start", 8, session_id=sid, value_ms=startup),
        ]
    events += [
        ev("playback_error", 5, session_id="s1", error_code="NETWORK_TIMEOUT"),
        ev("buffer_end", 5, session_id="s2", value_ms=500, device="mobile", cdn="fastly"),
        ev("buffer_end", 4, session_id="s3", value_ms=1500),
        ev("session_end", 3, session_id="s2", value_ms=10_000, device="mobile", cdn="fastly"),
        ev("session_end", 3, session_id="s3", value_ms=10_000),
        ev("bitrate_change", 6, session_id="s1", bitrate_kbps=2000),
        ev("bitrate_change", 6, session_id="s2", bitrate_kbps=4000),
    ]
    events += [ev("ad_request", 8, session_id=f"s{i}", ad_id=f"ad-{i}") for i in range(1, 5)]
    events += [ev("ad_impression", 8, session_id=f"s{i}", ad_id=f"ad-{i}") for i in range(1, 4)]
    events += [ev("ad_error", 8, session_id="s4", ad_id="ad-4")]
    # Outside the 60-minute window: must never be counted.
    events += [
        ev("session_start", 600, session_id="old"),
        ev("playback_error", 600, session_id="old"),
    ]
    assert post_events(*events).status_code == 201
