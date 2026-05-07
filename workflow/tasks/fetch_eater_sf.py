from __future__ import annotations

import logging
from typing import Any

from render_sdk import Retry

from app.sources.eater import fetch_eater_sf_articles
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="fetch-eater-sf",
    retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2),
    timeout_seconds=120,
)
async def fetch_eater_sf() -> list[dict[str, Any]]:
    logger.info("[workflow] fetching Eater SF...")
    items = await fetch_eater_sf_articles()
    logger.info("[workflow] Eater SF: %d raw articles", len(items))
    return [item.model_dump(by_alias=True) for item in items]
