"""SF Funcheap RSS scraper — events only."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.sources.rss import fetch_rss
from app.storage import NewEvent

FUNCHEAP_RSS = "https://sf.funcheap.com/feed/"

_TITLE_DATE_RE = re.compile(
    r"\s*\(([^)]+\d{4}|[^)]+\d{1,2}(?:st|nd|rd|th)?)\)\s*$",
    re.IGNORECASE,
)

_GENERIC_TITLE_RE = re.compile(
    r"^(search|category|tag|page \d+|free things to do|things to do)\b",
    re.IGNORECASE,
)


def normalize_funcheap_title_and_date(
    title: str, date_text: str
) -> tuple[str, str]:
    """Strip an embedded date from titles like 'Event Name (April 5, 2026)' and use
    it to override the RSS pubDate when it's more specific."""
    match = _TITLE_DATE_RE.search(title)
    if not match:
        return title.strip(), date_text
    embedded = match.group(1).strip()
    cleaned_title = _TITLE_DATE_RE.sub("", title).strip()
    return cleaned_title, embedded or date_text


def _is_too_old(pub_date: str | None, max_age_days: int = 60) -> bool:
    if not pub_date:
        return False
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(pub_date)
    except (ValueError, TypeError):
        return False
    if parsed is None:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return datetime.now(UTC) - parsed > timedelta(days=max_age_days)


def _format_pubdate_as_text(pub_date: str | None) -> str:
    if not pub_date:
        return datetime.now(UTC).strftime("%B %Y")
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(pub_date)
    except (ValueError, TypeError):
        return datetime.now(UTC).strftime("%B %Y")
    if parsed is None:
        return datetime.now(UTC).strftime("%B %Y")
    return parsed.strftime("%B %-d, %Y")


async def fetch_funcheap_events() -> list[NewEvent]:
    """Fetch SF Funcheap RSS, normalize titles, return NewEvents."""
    items = await fetch_rss(FUNCHEAP_RSS)
    results: list[NewEvent] = []
    for item in items:
        if not item.title:
            continue
        if _GENERIC_TITLE_RE.search(item.title):
            continue
        if _is_too_old(item.pub_date, max_age_days=60):
            continue

        date_text_raw = _format_pubdate_as_text(item.pub_date)
        title, date_text = normalize_funcheap_title_and_date(item.title, date_text_raw)
        if len(title) < 3:
            continue

        results.append(
            NewEvent(
                title=title,
                location="San Francisco",
                date=date_text,
                description=item.description or None,
                source_url=item.link or None,
            )
        )
    return results
