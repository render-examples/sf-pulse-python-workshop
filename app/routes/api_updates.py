"""Updates API — port of src/server/api/updates.ts."""

from __future__ import annotations

from fastapi import APIRouter

from app import storage

router = APIRouter(prefix="/api/updates", tags=["updates"])


@router.get("")
async def list_updates() -> list[storage.DataUpdate]:
    return await storage.get_recent_updates(50)


@router.get("/last-updated")
async def last_updated() -> dict:
    ts = await storage.get_latest_update_timestamp()
    return {"lastUpdated": ts.isoformat() if ts else None}
