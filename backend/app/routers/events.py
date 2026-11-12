from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps import SessionDep, require_ingest_key
from app.schemas import EventBatch, IngestResult
from app.services.ingest import ingest_events

router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post(
    "/events",
    status_code=201,
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_key)],
    summary="Ingest a batch of player telemetry events",
)
def post_events(batch: EventBatch, request: Request, session: SessionDep) -> IngestResult:
    max_batch = request.app.state.settings.max_batch_size
    if len(batch.events) > max_batch:
        raise HTTPException(413, detail=f"Batch too large (max {max_batch} events)")
    accepted = ingest_events(session, batch.events)
    request.app.state.metrics.observe_events(batch.events)
    return IngestResult(accepted=accepted)
