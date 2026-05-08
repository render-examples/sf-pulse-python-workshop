"""Shared route helpers — port of src/server/api/utils.ts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app import storage
from app.config import get_settings
from app.security import secrets_equal
from app.shared.types import InitialData, Restaurant


@dataclass
class InitialDataResult:
    restaurants: list[Restaurant]
    last_updated: str | None


async def get_initial_data() -> InitialData:
    restaurants_task = asyncio.create_task(storage.get_visible_restaurants())
    updates_task = asyncio.create_task(storage.get_recent_updates(1))
    restaurants, updates = await asyncio.gather(restaurants_task, updates_task)
    last_updated = updates[0].occurred_at.isoformat() if updates else None
    return InitialData(
        restaurants=[Restaurant.model_validate(r.model_dump()) for r in restaurants],
        lastUpdated=last_updated,
    )


def require_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    expected = get_settings().cron_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRON_SECRET is not configured",
        )
    if not secrets_equal(expected, x_cron_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-cron-secret",
        )
