"""Event API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import storage
from app.routes.utils import require_cron_secret
from app.sse import broadcast

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def list_events() -> list[storage.StoredEvent]:
    return await storage.get_visible_events()


@router.get("/events/{id}")
async def get_event(id: int) -> storage.StoredEvent:
    row = await storage.get_event_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return row


@router.delete("/events/{id}", dependencies=[Depends(require_cron_secret)])
async def delete_event(id: int) -> dict:
    existing = await storage.get_event_by_id(id)
    await storage.delete_event(id)

    version: str | None = None
    if existing:
        update = await storage.record_update("event", existing.title, "removed")
        version = update.occurred_at.isoformat()

    await broadcast(
        "events",
        {
            "version": version,
            "upserted": [],
            "deleted": [id],
            "summary": f"Removed event: {existing.title}" if existing else None,
        },
    )
    return {"ok": True}
