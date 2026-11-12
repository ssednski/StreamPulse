from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.deps import NowDep, SessionDep
from app.schemas import (
    BreakdownOut,
    Dimension,
    ErrorCountOut,
    EventOut,
    SessionTimelineOut,
    SummaryOut,
    TimeseriesOut,
)
from app.services import analytics

router = APIRouter(prefix="/v1", tags=["stats"])

WindowParam = Annotated[
    int,
    Query(ge=1, le=analytics.MAX_WINDOW_MINUTES, description="Look-back window in minutes."),
]


def _bounds(now: datetime, window_minutes: int, step_minutes: int | None = None):
    try:
        analytics.validate_window(window_minutes, step_minutes)
    except analytics.InvalidQueryError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    return analytics.window_bounds(now, window_minutes)


@router.get("/stats/summary", response_model=SummaryOut)
def summary(session: SessionDep, now: NowDep, window_minutes: WindowParam = 60):
    since, until = _bounds(now, window_minutes)
    return analytics.get_summary(session, since, until)


@router.get("/stats/timeseries", response_model=TimeseriesOut)
def timeseries(
    session: SessionDep,
    now: NowDep,
    window_minutes: WindowParam = 60,
    step_minutes: Annotated[int, Query(ge=1, le=1440)] = 5,
):
    since, until = _bounds(now, window_minutes, step_minutes)
    points = analytics.get_timeseries(session, since, until, step_minutes)
    return {"window_minutes": window_minutes, "step_minutes": step_minutes, "points": points}


@router.get("/stats/breakdown", response_model=BreakdownOut)
def breakdown(
    session: SessionDep,
    now: NowDep,
    dimension: Dimension = Dimension.device,
    window_minutes: WindowParam = 60,
):
    since, until = _bounds(now, window_minutes)
    rows = analytics.get_breakdown(session, since, until, dimension)
    return {"dimension": dimension, "window_minutes": window_minutes, "rows": rows}


@router.get("/stats/errors", response_model=list[ErrorCountOut])
def top_errors(
    session: SessionDep,
    now: NowDep,
    window_minutes: WindowParam = 60,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    since, until = _bounds(now, window_minutes)
    return analytics.get_top_errors(session, since, until, limit)


@router.get("/sessions/{session_id}", response_model=SessionTimelineOut)
def session_timeline(session_id: str, session: SessionDep):
    events = analytics.get_session_timeline(session, session_id)
    if not events:
        raise HTTPException(404, detail="Session not found")
    return SessionTimelineOut(
        session_id=session_id, events=[EventOut.model_validate(e) for e in events]
    )
