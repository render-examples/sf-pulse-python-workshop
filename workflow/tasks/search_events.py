from __future__ import annotations

import logging
from typing import Any

from render_sdk import Retry

from app.sources.ddg_search import search_events_ddg
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="search-events",
    retry=Retry(max_retries=2, wait_duration_ms=3000, backoff_scaling=2),
    timeout_seconds=60,
)
async def search_events() -> list[dict[str, Any]]:
    logger.info("[workflow] searching DuckDuckGo for events...")
    items = await search_events_ddg()
    logger.info("[workflow] DDG events: %d raw articles", len(items))
    return [item.model_dump(by_alias=True) for item in items]
