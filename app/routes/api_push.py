"""Push notifications API — port of src/server/api/push.ts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import storage
from app.push import get_vapid_public_key
from app.security import (
    PushKeysPayload,
    PushPreferencesUpdatePayload,
    PushSubscriptionPayload,
    SubscriptionLookup,
    UnsubscribePayload,
    is_trusted_push_endpoint,
)
from app.shared.catalog import normalize_push_preferences

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-key")
async def vapid_key() -> dict:
    try:
        return {"key": get_vapid_public_key()}
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err


@router.post("/subscribe")
async def subscribe(payload: PushSubscriptionPayload) -> storage.StoredPushSubscription:
    prefs = (
        payload.preferences.normalized() if payload.preferences else None
    )
    keys: PushKeysPayload = payload.keys
    return await storage.add_subscription(
        endpoint=payload.endpoint,
        keys={"p256dh": keys.p256dh, "auth": keys.auth},  # type: ignore[arg-type]
        preferences=prefs,
    )


@router.get("/subscription")
async def get_subscription(
    endpoint: str = Query(..., min_length=1, max_length=2048),
) -> storage.StoredPushSubscription:
    if not is_trusted_push_endpoint(endpoint):
        raise HTTPException(status_code=400, detail="Push endpoint must use a trusted web-push provider")
    SubscriptionLookup(endpoint=endpoint)  # validate via Pydantic
    sub = await storage.get_subscription_by_endpoint(endpoint)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.post("/preferences")
async def update_preferences(
    payload: PushPreferencesUpdatePayload,
) -> storage.StoredPushSubscription:
    sub = await storage.update_subscription_preferences(
        payload.endpoint,
        normalize_push_preferences(payload.preferences.model_dump()),
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.post("/unsubscribe")
async def unsubscribe(payload: UnsubscribePayload) -> dict:
    await storage.remove_subscription(payload.endpoint)
    return {"ok": True}
