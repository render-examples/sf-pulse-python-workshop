from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from render_sdk import Retry

from app.sources.sfist import fetch_sfist_restaurants
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="fetch-sfist",
    retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2),
    timeout_seconds=60,
)
async def fetch_sfist() -> list[dict[str, Any]]:
    logger.info("[workflow] fetching SFist...")
    items = await fetch_sfist_restaurants()
    logger.info("[workflow] SFist: %d candidates", len(items))
    return [asdict(item) for item in items]
