"""Fine Arts Museums of SF calendar scraper."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from app.sources.http import fetch_url
from app.storage import NewEvent

FAMSF_URL = "https://www.famsf.org/visit/calendar"

_GENERIC_TITLES = {
    "calendar",
    "events",
    "visit",
    "exhibitions",
    "menu",
    "search",
    "tickets",
    "membership",
    "shop",
    "donate",
    "newsletter",
}

_DATE_HINT_RE = re.compile(
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|spring|summer|fall|autumn|winter)",
    re.IGNORECASE,
)


def parse_museum_events(
    html: str, source_url: str, default_location: str
) -> list[NewEvent]:
    """Parse generic museum-style event cards: heading paired with date range."""
    if not html:
        return []
    tree = HTMLParser(html)
    events: list[NewEvent] = []
    seen: set[tuple[str, str]] = set()

    for heading in tree.css("h1, h2, h3, h4"):
        title = (heading.text(strip=True) or "").strip()
        if not title or len(title) < 3:
            continue
        if title.lower() in _GENERIC_TITLES:
            continue

        date_text = ""
        sibling = heading.next
        steps = 0
        while sibling is not None and steps < 6:
            text = (sibling.text(strip=True) or "").strip()
            if text and _DATE_HINT_RE.search(text):
                date_text = text
                break
            sibling = sibling.next
            steps += 1

        if not date_text:
            parent = heading.parent
            if parent is not None:
                container_text = parent.text(strip=True) or ""
                m = _DATE_HINT_RE.search(container_text)
                if m:
                    snippet_start = max(0, m.start() - 0)
                    snippet = container_text[snippet_start : m.end() + 25].strip()
                    if snippet:
                        date_text = snippet

        if not date_text:
            continue

        key = (title.lower(), date_text.lower())
        if key in seen:
            continue
        seen.add(key)

        events.append(
            NewEvent(
                title=title,
                location=default_location,
                date=date_text,
                source_url=source_url,
            )
        )
    return events


async def fetch_famsf_events() -> list[NewEvent]:
    """Fetch FAMSF calendar HTML and parse event cards."""
    html = await fetch_url(FAMSF_URL)
    if not html:
        return []
    lower = html.lower()
    default_location = "de Young Museum" if "de young" in lower else "Legion of Honor"
    return parse_museum_events(html, FAMSF_URL, default_location)
