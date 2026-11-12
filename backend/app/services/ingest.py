from datetime import UTC, datetime

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models import PlaybackEvent
from app.schemas import EventIn


def to_naive_utc(dt: datetime) -> datetime:
    """Normalise to naive UTC (naive input is assumed to already be UTC)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def ingest_events(session: Session, events: list[EventIn]) -> int:
    """Bulk-insert a batch in a single transaction and return how many rows were stored."""
    rows = []
    for e in events:
        ts = to_naive_utc(e.ts)
        rows.append(
            {
                "session_id": e.session_id,
                "event_type": e.event_type.value,
                "ts": ts,
                "ts_minute": ts.replace(second=0, microsecond=0),
                "device": e.device.value,
                "cdn": e.cdn,
                "content_id": e.content_id,
                "content_type": e.content_type,
                "bitrate_kbps": e.bitrate_kbps,
                "value_ms": e.value_ms,
                "ad_id": e.ad_id,
                "error_code": e.error_code,
            }
        )
    session.execute(insert(PlaybackEvent), rows)
    session.commit()
    return len(rows)
