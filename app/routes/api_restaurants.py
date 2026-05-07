"""Restaurant API — port of src/server/api/restaurants.ts."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import storage
from app.routes.utils import require_cron_secret
from app.sse import broadcast

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


@router.get("")
async def list_restaurants() -> list[storage.StoredRestaurant]:
    return await storage.get_visible_restaurants()


@router.get("/{id}")
async def get_one(id: int) -> storage.StoredRestaurant:
    row = await storage.get_restaurant_by_id(id)
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Restaurant not found")
    return row


@router.delete("/{id}", dependencies=[Depends(require_cron_secret)])
async def delete_one(id: int) -> dict:
    existing = await storage.get_restaurant_by_id(id)
    await storage.delete_restaurant(id)
    version: str | None = None
    summary: str | None = None
    if existing:
        update = await storage.record_update("restaurant", existing.name, "removed")
        version = update.occurred_at.isoformat()
        summary = f"Removed restaurant: {existing.name}"
    await broadcast(
        "restaurants",
        {"version": version, "upserted": [], "deleted": [id], "summary": summary},
    )
    return {"ok": True}
