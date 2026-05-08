from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from render_sdk import Retry

from app.sources.funcheap import fetch_funcheap_events
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="fetch-funcheap",
    retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2),
    timeout_seconds=120,
)
async def fetch_funcheap() -> list[dict[str, Any]]:
    logger.info("[workflow] fetching Funcheap...")
    events = await fetch_funcheap_events()
    logger.info("[workflow] Funcheap: %d events", len(events))
    return [asdict(e) for e in events]
