from __future__ import annotations

import logging
from typing import Any

from render_sdk import Retry

from app.refresh import apply_discovered_items as refresh_apply_discovered_items
from app.storage import NewRestaurant
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="apply-discovered-items",
    retry=Retry(max_retries=1, wait_duration_ms=5000),
    timeout_seconds=120,
)
async def apply_discovered_items(
    restaurants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    restaurant_objs = [NewRestaurant(**r) for r in (restaurants or [])]
    logger.info("[workflow] applying %d restaurants", len(restaurant_objs))
    try:
        result = await refresh_apply_discovered_items(restaurants=restaurant_objs)
    except Exception:
        logger.exception("[workflow] apply_discovered_items failed")
        raise

    payload = {
        "added_restaurants": list(result.added_restaurants),
        "updated_restaurants": list(result.updated_restaurants),
    }
    logger.info("[workflow] apply result: %s", payload)
    return payload
