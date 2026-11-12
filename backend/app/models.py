from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlaybackEvent(Base):
    """One telemetry beacon from a video player (all timestamps are naive UTC)."""

    __tablename__ = "playback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    # ts truncated to the minute: lets us bucket time series with a plain GROUP BY,
    # which behaves identically on SQLite and PostgreSQL.
    ts_minute: Mapped[datetime] = mapped_column(DateTime)
    device: Mapped[str] = mapped_column(String(32))
    cdn: Mapped[str] = mapped_column(String(32))
    content_id: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(8))
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_events_type_minute", "event_type", "ts_minute"),)
