"""Read-side analytics. All KPI maths lives here so REST and GraphQL share one implementation.

KPI definitions:
  * error_rate      playback_error events / sessions started
  * ad_fill_rate    ad_impression events / ad_request events
  * avg_startup_ms  mean value_ms of playback_start events (video start time)
  * rebuffer_ratio  total stall time (buffer_end) / total watch time (session_end);
                    an approximation that is noisy over very short windows
"""

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PlaybackEvent as E
from app.schemas import Dimension
from app.services.ingest import to_naive_utc

EPOCH = datetime(1970, 1, 1)
MAX_WINDOW_MINUTES = 7 * 24 * 60
MAX_POINTS = 1500

# event_type -> (row count, sum of value_ms)
Rollup = Mapping[str, tuple[int, int]]


class InvalidQueryError(ValueError):
    """The requested window/step is outside what the API supports."""


@dataclass(frozen=True)
class KPIs:
    sessions: int
    errors: int
    error_rate: float
    ad_requests: int
    ad_impressions: int
    ad_fill_rate: float
    avg_startup_ms: float
    rebuffer_ratio: float


@dataclass(frozen=True)
class Summary(KPIs):
    p95_startup_ms: float
    avg_bitrate_kbps: float


@dataclass(frozen=True)
class TimePoint(KPIs):
    ts: datetime


@dataclass(frozen=True)
class BreakdownRow(KPIs):
    key: str


@dataclass(frozen=True)
class ErrorCount:
    error_code: str
    count: int


def validate_window(window_minutes: int, step_minutes: int | None = None) -> None:
    if not 1 <= window_minutes <= MAX_WINDOW_MINUTES:
        raise InvalidQueryError(f"window_minutes must be between 1 and {MAX_WINDOW_MINUTES}")
    if step_minutes is not None:
        if not 1 <= step_minutes <= 1440:
            raise InvalidQueryError("step_minutes must be between 1 and 1440")
        if window_minutes / step_minutes > MAX_POINTS:
            raise InvalidQueryError(f"window/step would return more than {MAX_POINTS} points")


def window_bounds(now: datetime, window_minutes: int) -> tuple[datetime, datetime]:
    until = to_naive_utc(now)
    return until - timedelta(minutes=window_minutes), until


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def compute_kpis(rollup: Rollup) -> KPIs:
    zero = (0, 0)
    sessions = rollup.get("session_start", zero)[0]
    errors = rollup.get("playback_error", zero)[0]
    plays, startup_sum = rollup.get("playback_start", zero)
    ad_requests = rollup.get("ad_request", zero)[0]
    ad_impressions = rollup.get("ad_impression", zero)[0]
    stall_ms = rollup.get("buffer_end", zero)[1]
    watch_ms = rollup.get("session_end", zero)[1]
    return KPIs(
        sessions=sessions,
        errors=errors,
        error_rate=round(_safe_div(errors, sessions), 4),
        ad_requests=ad_requests,
        ad_impressions=ad_impressions,
        ad_fill_rate=round(_safe_div(ad_impressions, ad_requests), 4),
        avg_startup_ms=round(_safe_div(startup_sum, plays), 1),
        rebuffer_ratio=round(_safe_div(stall_ms, watch_ms), 4),
    )


def _in_window(since: datetime, until: datetime):
    return (E.ts >= since, E.ts <= until)


def _startup_percentile(session: Session, since: datetime, until: datetime, q: float) -> float:
    """Nearest-rank percentile using ORDER BY/OFFSET, so it works on any SQL backend."""
    base = select(E.value_ms).where(E.event_type == "playback_start", *_in_window(since, until))
    n = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    if n == 0:
        return 0.0
    index = max(math.ceil(q * n) - 1, 0)
    value = session.scalar(base.order_by(E.value_ms).limit(1).offset(index))
    return float(value or 0)


def get_summary(session: Session, since: datetime, until: datetime) -> Summary:
    stmt = (
        select(E.event_type, func.count(), func.coalesce(func.sum(E.value_ms), 0))
        .where(*_in_window(since, until))
        .group_by(E.event_type)
    )
    rollup = {t: (int(c), int(s)) for t, c, s in session.execute(stmt)}
    avg_bitrate = session.scalar(
        select(func.avg(E.bitrate_kbps)).where(
            E.event_type == "bitrate_change", *_in_window(since, until)
        )
    )
    return Summary(
        **vars(compute_kpis(rollup)),
        p95_startup_ms=_startup_percentile(session, since, until, 0.95),
        avg_bitrate_kbps=round(float(avg_bitrate or 0), 1),
    )


def _bucket_start(dt: datetime, step_minutes: int) -> datetime:
    minutes = int((dt - EPOCH).total_seconds() // 60)
    return EPOCH + timedelta(minutes=minutes - minutes % step_minutes)


def get_timeseries(
    session: Session, since: datetime, until: datetime, step_minutes: int
) -> list[TimePoint]:
    """Per-minute aggregates rolled up in Python into `step_minutes` buckets, zero-filled."""
    stmt = (
        select(E.ts_minute, E.event_type, func.count(), func.coalesce(func.sum(E.value_ms), 0))
        .where(*_in_window(since, until))
        .group_by(E.ts_minute, E.event_type)
    )
    buckets: dict[datetime, dict[str, tuple[int, int]]] = defaultdict(dict)
    for ts_minute, event_type, count, total in session.execute(stmt):
        bucket = buckets[_bucket_start(ts_minute, step_minutes)]
        prev_count, prev_total = bucket.get(event_type, (0, 0))
        bucket[event_type] = (prev_count + int(count), prev_total + int(total))

    points: list[TimePoint] = []
    cursor = _bucket_start(since, step_minutes)
    while cursor <= until:
        kpis = compute_kpis(buckets.get(cursor, {}))
        points.append(TimePoint(**vars(kpis), ts=cursor.replace(tzinfo=UTC)))
        cursor += timedelta(minutes=step_minutes)
    return points


def get_breakdown(
    session: Session, since: datetime, until: datetime, dimension: Dimension
) -> list[BreakdownRow]:
    column = getattr(E, dimension.value)  # safe: dimension is a closed enum
    stmt = (
        select(column, E.event_type, func.count(), func.coalesce(func.sum(E.value_ms), 0))
        .where(*_in_window(since, until))
        .group_by(column, E.event_type)
    )
    groups: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for key, event_type, count, total in session.execute(stmt):
        groups[key][event_type] = (int(count), int(total))
    rows = [BreakdownRow(**vars(compute_kpis(r)), key=k) for k, r in groups.items()]
    return sorted(rows, key=lambda r: (-r.sessions, r.key))


def get_top_errors(
    session: Session, since: datetime, until: datetime, limit: int = 10
) -> list[ErrorCount]:
    count = func.count()
    stmt = (
        select(E.error_code, count)
        .where(E.event_type == "playback_error", *_in_window(since, until))
        .group_by(E.error_code)
        .order_by(count.desc(), E.error_code)
        .limit(limit)
    )
    return [ErrorCount(error_code=code, count=int(n)) for code, n in session.execute(stmt)]


def get_session_timeline(session: Session, session_id: str) -> list[E]:
    stmt = select(E).where(E.session_id == session_id).order_by(E.ts, E.id)
    return list(session.scalars(stmt))
