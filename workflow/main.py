from __future__ import annotations

from workflow._app import app
from workflow.tasks import (
    apply_discovered_items,
    daily_refresh,
    fetch_eater_sf,
    fetch_michelin,
    fetch_sfist,
    search_restaurants,
)

__all__ = [
    "app",
    "apply_discovered_items",
    "daily_refresh",
    "fetch_eater_sf",
    "fetch_michelin",
    "fetch_sfist",
    "search_restaurants",
]


if __name__ == "__main__":
    app.start()
