"""Prometheus instrumentation: business metrics (QoE, ads) and HTTP metrics."""

import threading
from collections.abc import Iterable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)

from app.schemas import EventIn, EventType


class LabelGuard:
    """Caps label cardinality: after `limit` distinct values, new ones collapse to "other".

    Client-controlled values (CDN names, error codes) must never be able to create
    unbounded Prometheus time series.
    """

    def __init__(self, limit: int = 50) -> None:
        self._limit = limit
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def __call__(self, value: str) -> str:
        with self._lock:
            if value in self._seen:
                return value
            if len(self._seen) < self._limit:
                self._seen.add(value)
                return value
        return "other"


class Metrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        # A registry per app instance keeps tests isolated from each other.
        self.registry = registry or CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        self._cdn = LabelGuard()
        self._error_code = LabelGuard()

        self.events_ingested = Counter(
            "streampulse_events_ingested_total",
            "Telemetry events accepted, by type and device.",
            ["event_type", "device"],
            registry=self.registry,
        )
        self.sessions_started = Counter(
            "streampulse_sessions_started_total",
            "Playback sessions started.",
            ["device", "cdn"],
            registry=self.registry,
        )
        self.startup_seconds = Histogram(
            "streampulse_playback_startup_seconds",
            "Video start time (time to first frame).",
            buckets=(0.25, 0.5, 1, 2, 3, 5, 8, 13),
            registry=self.registry,
        )
        self.rebuffer_seconds = Histogram(
            "streampulse_rebuffer_seconds",
            "Duration of individual rebuffering stalls.",
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
            registry=self.registry,
        )
        self.playback_errors = Counter(
            "streampulse_playback_errors_total",
            "Fatal playback errors.",
            ["cdn", "error_code"],
            registry=self.registry,
        )
        self.ad_requests = Counter(
            "streampulse_ad_requests_total", "Ad requests.", ["device"], registry=self.registry
        )
        self.ad_impressions = Counter(
            "streampulse_ad_impressions_total",
            "Ad impressions.",
            ["device"],
            registry=self.registry,
        )
        self.ad_errors = Counter(
            "streampulse_ad_errors_total", "Ad errors.", ["device"], registry=self.registry
        )
        self.http_requests = Counter(
            "streampulse_http_requests_total",
            "HTTP requests handled by the API.",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "streampulse_http_request_duration_seconds",
            "HTTP request latency.",
            ["method", "path"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
            registry=self.registry,
        )

    def observe_events(self, events: Iterable[EventIn]) -> None:
        for e in events:
            device = e.device.value
            self.events_ingested.labels(e.event_type.value, device).inc()
            match e.event_type:
                case EventType.session_start:
                    self.sessions_started.labels(device, self._cdn(e.cdn)).inc()
                case EventType.playback_start:
                    self.startup_seconds.observe((e.value_ms or 0) / 1000)
                case EventType.buffer_end:
                    self.rebuffer_seconds.observe((e.value_ms or 0) / 1000)
                case EventType.playback_error:
                    self.playback_errors.labels(
                        self._cdn(e.cdn), self._error_code(e.error_code or "UNKNOWN")
                    ).inc()
                case EventType.ad_request:
                    self.ad_requests.labels(device).inc()
                case EventType.ad_impression:
                    self.ad_impressions.labels(device).inc()
                case EventType.ad_error:
                    self.ad_errors.labels(device).inc()

    def observe_http(self, method: str, path: str, status: int, seconds: float) -> None:
        self.http_requests.labels(method, path, str(status)).inc()
        self.http_duration.labels(method, path).observe(seconds)
