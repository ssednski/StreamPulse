"""GraphQL facade over the same analytics service the REST API uses."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

import strawberry
from fastapi import Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from app.schemas import Dimension
from app.services import analytics


@strawberry.enum(name="Dimension")
class DimensionEnum(Enum):
    DEVICE = "device"
    CDN = "cdn"
    CONTENT_TYPE = "content_type"


@strawberry.type
class KPIs:
    sessions: int
    errors: int
    error_rate: float
    ad_requests: int
    ad_impressions: int
    ad_fill_rate: float
    avg_startup_ms: float
    rebuffer_ratio: float


@strawberry.type
class Summary(KPIs):
    p95_startup_ms: float
    avg_bitrate_kbps: float


@strawberry.type
class TimePoint(KPIs):
    ts: datetime


@strawberry.type
class BreakdownRow(KPIs):
    key: str


@strawberry.type
class ErrorCount:
    error_code: str
    count: int


async def get_context(request: Request) -> dict[str, Any]:
    return {
        "session_factory": request.app.state.session_factory,
        "now": request.app.state.clock(),
    }


async def _run[T](info: Info, fn: Callable[[Session], T]) -> T:
    """Run blocking SQLAlchemy work in a worker thread so the event loop stays free."""
    factory = info.context["session_factory"]

    def work() -> T:
        with factory() as session:
            return fn(session)

    return await run_in_threadpool(work)


def _bounds(info: Info, window_minutes: int, step_minutes: int | None = None):
    analytics.validate_window(window_minutes, step_minutes)  # raises -> GraphQL error
    return analytics.window_bounds(info.context["now"], window_minutes)


@strawberry.type
class Query:
    @strawberry.field
    async def summary(self, info: Info, window_minutes: int = 60) -> Summary:
        since, until = _bounds(info, window_minutes)
        result = await _run(info, lambda s: analytics.get_summary(s, since, until))
        return Summary(**asdict(result))

    @strawberry.field
    async def timeseries(
        self, info: Info, window_minutes: int = 60, step_minutes: int = 5
    ) -> list[TimePoint]:
        since, until = _bounds(info, window_minutes, step_minutes)
        points = await _run(info, lambda s: analytics.get_timeseries(s, since, until, step_minutes))
        return [TimePoint(**asdict(p)) for p in points]

    @strawberry.field
    async def breakdown(
        self,
        info: Info,
        dimension: DimensionEnum = DimensionEnum.DEVICE,
        window_minutes: int = 60,
    ) -> list[BreakdownRow]:
        since, until = _bounds(info, window_minutes)
        column = Dimension(dimension.value)
        rows = await _run(info, lambda s: analytics.get_breakdown(s, since, until, column))
        return [BreakdownRow(**asdict(r)) for r in rows]

    @strawberry.field
    async def top_errors(
        self, info: Info, window_minutes: int = 60, limit: int = 10
    ) -> list[ErrorCount]:
        since, until = _bounds(info, window_minutes)
        rows = await _run(info, lambda s: analytics.get_top_errors(s, since, until, limit))
        return [ErrorCount(**asdict(r)) for r in rows]


schema = strawberry.Schema(query=Query)


def make_graphql_router() -> GraphQLRouter:
    return GraphQLRouter(schema, context_getter=get_context)
