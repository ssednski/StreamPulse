"""Pure session/event generation (no I/O) so behaviour is easy to unit test with a seeded RNG."""

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

DEVICES = {"tv": 0.35, "mobile": 0.30, "web": 0.20, "set_top_box": 0.10, "console": 0.05}
CDNS = {"akamai": 0.40, "fastly": 0.30, "cloudfront": 0.30}
BITRATES_KBPS = [800, 1500, 3000, 5000, 8000]
ERROR_CODES = {
    "NETWORK_TIMEOUT": 0.35,
    "DRM_LICENSE_FAILED": 0.20,
    "CDN_5XX": 0.20,
    "DECODER_ERROR": 0.15,
    "MANIFEST_404": 0.10,
}
# Median video start time per device, in seconds.
MEDIAN_STARTUP_S = {"tv": 1.6, "mobile": 2.2, "web": 1.9, "set_top_box": 2.4, "console": 1.5}


@dataclass(frozen=True)
class Profile:
    catalog_size: int = 60
    base_error_rate: float = 0.015
    ad_fill_rate: float = 0.93
    preroll_prob: float = 0.8
    median_watch_s: float = 90.0  # kept short so dashboards fill up quickly
    midroll_every_s: float = 60.0
    stalls_per_minute: float = 0.35
    # An "incident" degrades one CDN from `incident_start` onwards.
    incident_cdn: str | None = None
    incident_start: datetime | None = None

    def incident_active(self, cdn: str, at: datetime) -> bool:
        return (
            self.incident_cdn == cdn
            and self.incident_start is not None
            and at >= self.incident_start
        )


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm; fine for the small rates used here."""
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def build_session(rng: random.Random, started_at: datetime, profile: Profile) -> list[dict]:
    """Return every event of one viewing session, with timestamps (possibly in the future)."""
    device = weighted_choice(rng, DEVICES)
    cdn = weighted_choice(rng, CDNS)
    title = rng.randrange(profile.catalog_size)
    incident = profile.incident_active(cdn, started_at)

    base = {
        "session_id": f"s-{rng.getrandbits(48):012x}",
        "device": device,
        "cdn": cdn,
        "content_id": f"title-{title:03d}",
        "content_type": "live" if title % 10 < 3 else "vod",
    }
    events: list[dict] = []

    def add(offset_ms: int, event_type: str, **extra) -> None:
        events.append(
            {**base, "event_type": event_type, "ts": started_at + timedelta(milliseconds=offset_ms)}
            | extra
        )

    def maybe_ad(offset_ms: int) -> int:
        """Emit one ad request (+ impression or error); return the offset after the ad."""
        ad_id = f"ad-{rng.randrange(500):03d}"
        add(offset_ms, "ad_request", ad_id=ad_id)
        offset_ms += rng.randint(150, 600)
        if rng.random() < profile.ad_fill_rate:
            add(offset_ms, "ad_impression", ad_id=ad_id)
            return offset_ms + rng.choice([15_000, 30_000])
        add(offset_ms, "ad_error", ad_id=ad_id)
        return offset_ms

    add(0, "session_start")
    cursor = maybe_ad(0) if rng.random() < profile.preroll_prob else 0

    startup_ms = int(rng.lognormvariate(math.log(MEDIAN_STARTUP_S[device] * 1000), 0.5))
    if incident:
        startup_ms = int(startup_ms * 2.5)
    play_at = cursor + startup_ms
    bitrate = rng.choice(BITRATES_KBPS[:3])
    add(play_at, "playback_start", value_ms=startup_ms, bitrate_kbps=bitrate)

    watch_ms = int(min(rng.lognormvariate(math.log(profile.median_watch_s * 1000), 0.8), 7_200_000))
    watch_ms = max(watch_ms, 5_000)

    error_rate = profile.base_error_rate * (8 if incident else 1)
    if rng.random() < error_rate:
        watch_ms = rng.randint(1_000, watch_ms)
        add(play_at + watch_ms, "playback_error", error_code=weighted_choice(rng, ERROR_CODES))

    for _ in range(rng.randint(0, 3)):
        pool = BITRATES_KBPS[:2] if incident else BITRATES_KBPS
        add(play_at + rng.randint(1_000, watch_ms), "bitrate_change", bitrate_kbps=rng.choice(pool))

    minutes = watch_ms / 60_000
    stall_rate = profile.stalls_per_minute * (4 if incident else 1)
    for _ in range(min(poisson(rng, stall_rate * minutes), 12)):
        add(
            play_at + rng.randint(1_000, watch_ms),
            "buffer_end",
            value_ms=int(rng.lognormvariate(math.log(700), 0.7)),
        )

    for i in range(int(watch_ms // (profile.midroll_every_s * 1000))):
        maybe_ad(play_at + int((i + 1) * profile.midroll_every_s * 1000))

    add(play_at + watch_ms, "session_end", value_ms=watch_ms)
    return sorted(events, key=lambda e: e["ts"])


def iter_backfill(
    rng: random.Random, now: datetime, minutes: int, sessions_per_second: float, profile: Profile
) -> Iterator[dict]:
    """Yield historical events (all with ts <= now) for sessions spread over the last `minutes`."""
    total = int(minutes * 60 * sessions_per_second)
    for _ in range(total):
        started_at = now - timedelta(seconds=rng.uniform(0, minutes * 60))
        for event in build_session(rng, started_at, profile):
            if event["ts"] <= now:  # sessions still in progress have no end event yet
                yield event
