"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import close_pool
from app.routes import (
    api_health,
    api_push,
    api_restaurants,
    api_rss,
    api_sse,
    api_updates,
    pages,
)
from app.sse import initialize_realtime, shutdown_realtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("app")

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.redis_url:
        try:
            await initialize_realtime()
            log.info("[realtime] Redis pub/sub ready")
        except Exception as err:  # noqa: BLE001
            log.warning("[realtime] Redis init failed; falling back to in-process: %s", err)
    yield
    await shutdown_realtime()
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SF Pulse",
        description="SF restaurant openings tracker (Python)",
        lifespan=lifespan,
    )

    # API routers
    app.include_router(api_health.router)
    app.include_router(api_restaurants.router)
    app.include_router(api_push.router)
    app.include_router(api_updates.router)
    app.include_router(api_rss.router)
    app.include_router(api_sse.router)

    # Page routes (HTML)
    app.include_router(pages.router)

    # Static files: /static/* and /diagram/* (built React bundle)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    diagram_dir = STATIC_DIR / "diagram"
    if diagram_dir.exists():
        app.mount("/diagram", StaticFiles(directory=str(diagram_dir), html=True), name="diagram")

    return app


app = create_app()
