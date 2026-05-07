from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from render_sdk import Retry

from app.sources.famsf import fetch_famsf_events
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="fetch-famsf",
    retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2),
    timeout_seconds=60,
)
async def fetch_famsf() -> list[dict[str, Any]]:
    logger.info("[workflow] fetching FAMSF...")
    items = await fetch_famsf_events()
    logger.info("[workflow] FAMSF: %d events", len(items))
    return [asdict(item) for item in items]
