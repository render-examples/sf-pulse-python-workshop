"""Render Cron trigger — starts the daily-refresh workflow task and polls until done."""

from __future__ import annotations

import logging
import sys
import time

from render_sdk import Render

from app.config import get_settings

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "succeeded", "failed", "canceled"}
POLL_SECONDS = 15
TIMEOUT_SECONDS = 30 * 60


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()

    token = settings.render_api_key
    if not token:
        logger.error("[cron] RENDER_API_KEY is required")
        return 1

    slug = settings.sf_pulse_workflow_slug
    if not slug:
        logger.error("[cron] SF_PULSE_WORKFLOW_SLUG is required")
        return 1

    client = Render(token=token)
    task_slug = f"{slug}/daily-refresh"
    logger.info("[cron] triggering workflow %s...", task_slug)

    try:
        task_run = client.workflows.start_task(task_slug, [])
        task_run_id = task_run.id
        logger.info("[cron] task run started: %s", task_run_id)

        deadline = time.monotonic() + TIMEOUT_SECONDS

        while True:
            time.sleep(POLL_SECONDS)

            if time.monotonic() > deadline:
                logger.error("[cron] timed out waiting for task run %s", task_run_id)
                return 1

            run = client.workflows.get_task_run(task_run_id)
            status = getattr(run, "status", "unknown")
            logger.info("[cron] status: %s", status)

            if status in TERMINAL_STATUSES:
                if status in {"failed", "canceled"}:
                    logger.error("[cron] workflow failed: %r", run)
                    return 1
                logger.info("[cron] workflow completed: %s", status)
                return 0
    except Exception:
        logger.exception("[cron] workflow failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
