"""DuckDuckGo HTML search wrappers — port of bin/cron-refresh/restaurants.ts.

`searchRestaurantsRaw` in TS returns a single RawArticle whose bodyText is the
stripped DDG search result page; the LLM pipeline then mines it.
This module mirrors that contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.sources.http import ddg_search, extract_body_text
from app.sources.types import RawArticle


def _month_year() -> str:
    return datetime.now(UTC).strftime("%B %Y")


async def search_restaurants_ddg() -> list[RawArticle]:
    """Run the canonical 'new restaurant openings San Francisco {Month Year}' query."""
    month_year = _month_year()
    html = await ddg_search(f"new restaurant openings San Francisco {month_year}")
    return [
        RawArticle(
            source="ddg",
            url="",
            title=f"DDG: new restaurant openings San Francisco {month_year}",
            pubDate=None,
            bodyText=extract_body_text(html) if html else "",
        )
    ]
