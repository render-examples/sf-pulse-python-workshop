"""California Academy of Sciences events scraper."""

from __future__ import annotations

from app.sources.famsf import parse_museum_events
from app.sources.http import fetch_url
from app.storage import NewEvent

CAL_ACADEMY_URL = "https://www.calacademy.org/events"


async def fetch_cal_academy_events() -> list[NewEvent]:
    """Fetch Cal Academy events HTML, reuse parse_museum_events."""
    html = await fetch_url(CAL_ACADEMY_URL)
    if not html:
        return []
    return parse_museum_events(html, CAL_ACADEMY_URL, "California Academy of Sciences")
