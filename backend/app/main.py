import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app import __version__
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.graphql_api import make_graphql_router
from app.metrics import Metrics
from app.models import Base
from app.routers import events, stats

logger = logging.getLogger("streampulse")


def create_app(
    settings: Settings | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)  # an Alembic migration would replace this in production
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("StreamPulse %s starting", __version__)
        yield
        engine.dispose()

    app = FastAPI(
        title="StreamPulse",
        version=__version__,
        description="Playback and ad-delivery telemetry: ingest, analytics and observability.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.clock = clock or (lambda: datetime.now(UTC))
    app.state.metrics = metrics

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def record_http_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Use the route template ("/v1/sessions/{session_id}"), never the raw path,
            # so label cardinality stays bounded.
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            metrics.observe_http(request.method, path, status, time.perf_counter() - start)

    app.include_router(events.router)
    app.include_router(stats.router)
    app.include_router(make_graphql_router(), prefix="/graphql")

    @app.get("/healthz", tags=["ops"], summary="Liveness probe")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"], summary="Readiness probe (checks the database)")
    def readyz() -> dict[str, str]:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("readiness check failed")
            raise HTTPException(503, detail="database unavailable") from exc
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app
