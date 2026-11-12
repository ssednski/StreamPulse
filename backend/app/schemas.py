from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(StrEnum):
    session_start = "session_start"
    playback_start = "playback_start"  # value_ms = video start time
    buffer_end = "buffer_end"  # value_ms = stall duration
    bitrate_change = "bitrate_change"  # bitrate_kbps = new rendition
    ad_request = "ad_request"
    ad_impression = "ad_impression"
    ad_error = "ad_error"
    playback_error = "playback_error"  # error_code required
    session_end = "session_end"  # value_ms = watch time


class Device(StrEnum):
    tv = "tv"
    mobile = "mobile"
    web = "web"
    console = "console"
    set_top_box = "set_top_box"


class Dimension(StrEnum):
    device = "device"
    cdn = "cdn"
    content_type = "content_type"


_NEEDS_VALUE = {EventType.playback_start, EventType.buffer_end, EventType.session_end}
_NEEDS_AD = {EventType.ad_request, EventType.ad_impression, EventType.ad_error}


class EventIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    event_type: EventType
    ts: datetime
    device: Device
    cdn: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    content_id: str = Field(min_length=1, max_length=64)
    content_type: Literal["live", "vod"] = "vod"
    bitrate_kbps: int | None = Field(default=None, ge=0, le=100_000)
    value_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    ad_id: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=32, pattern=r"^[A-Z0-9_]+$")

    @model_validator(mode="after")
    def _check_required_fields(self) -> "EventIn":
        if self.event_type in _NEEDS_VALUE and self.value_ms is None:
            raise ValueError(f"value_ms is required for {self.event_type.value} events")
        if self.event_type in _NEEDS_AD and not self.ad_id:
            raise ValueError(f"ad_id is required for {self.event_type.value} events")
        if self.event_type is EventType.playback_error and not self.error_code:
            raise ValueError("error_code is required for playback_error events")
        if self.event_type is EventType.bitrate_change and self.bitrate_kbps is None:
            raise ValueError("bitrate_kbps is required for bitrate_change events")
        return self


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1)


class IngestResult(BaseModel):
    accepted: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    ts: datetime
    device: str
    cdn: str
    content_id: str
    content_type: str
    bitrate_kbps: int | None
    value_ms: int | None
    ad_id: str | None
    error_code: str | None

    @field_validator("ts")
    @classmethod
    def _as_utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class KPIsOut(BaseModel):
    sessions: int
    errors: int
    error_rate: float
    ad_requests: int
    ad_impressions: int
    ad_fill_rate: float
    avg_startup_ms: float
    rebuffer_ratio: float


class SummaryOut(KPIsOut):
    p95_startup_ms: float
    avg_bitrate_kbps: float


class TimePointOut(KPIsOut):
    ts: datetime


class TimeseriesOut(BaseModel):
    window_minutes: int
    step_minutes: int
    points: list[TimePointOut]


class BreakdownRowOut(KPIsOut):
    key: str


class BreakdownOut(BaseModel):
    dimension: Dimension
    window_minutes: int
    rows: list[BreakdownRowOut]


class ErrorCountOut(BaseModel):
    error_code: str
    count: int


class SessionTimelineOut(BaseModel):
    session_id: str
    events: list[EventOut]
