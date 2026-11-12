import secrets
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session


def get_now(request: Request) -> datetime:
    """Current time from the app's clock (injectable so tests are deterministic)."""
    return request.app.state.clock()


def require_ingest_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.ingest_api_key
    if not expected:
        return
    if not secrets.compare_digest((x_api_key or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
