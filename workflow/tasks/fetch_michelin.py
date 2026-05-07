from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from render_sdk import Retry

from app.sources.michelin import fetch_michelin_restaurants
from app.storage import get_cron_run, mark_cron_run
from workflow._app import app

logger = logging.getLogger(__name__)

MICHELIN_CRON_JOB = "michelin_california_selection"
THREE_DAYS_SECONDS = 3 * 24 * 60 * 60


def _is_cron_job_due(last_ran_at: datetime | None, interval_seconds: float) -> bool:
    if last_ran_at is None:
        return True
    now = datetime.now(UTC)
    last = last_ran_at if last_ran_at.tzinfo else last_ran_at.replace(tzinfo=UTC)
    return (now - last).total_seconds() >= interval_seconds


@app.task(
    name="fetch-michelin",
    retry=Retry(max_retries=2, wait_duration_ms=5000, backoff_scaling=2),
    timeout_seconds=120,
)
async def fetch_michelin() -> list[dict[str, Any]]:
    try:
        run = await get_cron_run(MICHELIN_CRON_JOB)
    except Exception:
        logger.exception("[workflow] get_cron_run failed")
        raise

    last_ran_at = run.last_ran_at if run else None
    if not _is_cron_job_due(last_ran_at, THREE_DAYS_SECONDS):
        logger.info("[workflow] michelin check not due, skipping")
        return []

    logger.info("[workflow] checking Michelin California selection...")
    items = await fetch_michelin_restaurants()

    try:
        await mark_cron_run(MICHELIN_CRON_JOB)
    except Exception:
        logger.exception("[workflow] mark_cron_run failed")
        raise

    logger.info("[workflow] Michelin: %d candidates", len(items))
    return [asdict(item) for item in items]
