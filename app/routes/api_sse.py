"""SSE realtime stream — port of src/server/api/events-stream.ts."""

from __future__ import annotations

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.sse import hub, initialize_realtime

router = APIRouter(prefix="/api", tags=["realtime"])


@router.get("/events-stream")
async def events_stream() -> EventSourceResponse:
    await initialize_realtime()
    return EventSourceResponse(hub.stream())
