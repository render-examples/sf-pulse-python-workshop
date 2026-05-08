"""Filter parsing/application — port of shared/filters.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

from app.shared.catalog import derive_event_category, derive_event_neighborhood
from app.shared.dates import today_utc
from app.shared.types import Restaurant, SFEvent

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class RestaurantFilters:
    query: str = ""
    neighborhoods: list[str] = field(default_factory=list)
    cuisines: list[str] = field(default_factory=list)
    upcoming_only: bool = False
    from_date: str = ""
    to_date: str = ""


@dataclass
class EventFilters:
    query: str = ""
    neighborhoods: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    upcoming_only: bool = False
    from_date: str = ""
    to_date: str = ""


@dataclass
class HomeFilters:
    restaurants: RestaurantFilters = field(default_factory=RestaurantFilters)
    events: EventFilters = field(default_factory=EventFilters)


DEFAULT_RESTAURANT_FILTERS = RestaurantFilters()
DEFAULT_EVENT_FILTERS = EventFilters()
DEFAULT_HOME_FILTERS = HomeFilters()


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    seen: list[str] = []
    for item in value.split(","):
        s = item.strip()
        if s and s not in seen:
            seen.append(s)
    return seen


def _normalize_iso_date(value: str | None) -> str:
    return value if value and _ISO_DATE_RE.match(value) else ""


def _get(params: dict[str, str], key: str) -> str | None:
    return params.get(key)


def parse_home_filters(params: dict[str, str]) -> HomeFilters:
    return HomeFilters(
        restaurants=RestaurantFilters(
            query=(_get(params, "r-q") or "").strip(),
            neighborhoods=_parse_list(_get(params, "r-neighborhood")),
            cuisines=_parse_list(_get(params, "r-cuisine")),
            upcoming_only=_get(params, "r-upcoming") == "1",
            from_date=_normalize_iso_date(_get(params, "r-from")),
            to_date=_normalize_iso_date(_get(params, "r-to")),
        ),
        events=EventFilters(
            query=(_get(params, "e-q") or "").strip(),
            neighborhoods=_parse_list(_get(params, "e-neighborhood")),
            categories=_parse_list(_get(params, "e-category")),
            upcoming_only=_get(params, "e-upcoming") == "1",
            from_date=_normalize_iso_date(_get(params, "e-from")),
            to_date=_normalize_iso_date(_get(params, "e-to")),
        ),
    )


def serialize_home_filters(filters: HomeFilters) -> str:
    pairs: list[tuple[str, str]] = []
    r = filters.restaurants
    if r.query:
        pairs.append(("r-q", r.query))
    if r.neighborhoods:
        pairs.append(("r-neighborhood", ",".join(r.neighborhoods)))
    if r.cuisines:
        pairs.append(("r-cuisine", ",".join(r.cuisines)))
    if r.upcoming_only:
        pairs.append(("r-upcoming", "1"))
    if r.from_date:
        pairs.append(("r-from", r.from_date))
    if r.to_date:
        pairs.append(("r-to", r.to_date))

    e = filters.events
    if e.query:
        pairs.append(("e-q", e.query))
    if e.neighborhoods:
        pairs.append(("e-neighborhood", ",".join(e.neighborhoods)))
    if e.categories:
        pairs.append(("e-category", ",".join(e.categories)))
    if e.upcoming_only:
        pairs.append(("e-upcoming", "1"))
    if e.from_date:
        pairs.append(("e-from", e.from_date))
    if e.to_date:
        pairs.append(("e-to", e.to_date))
    return urlencode(pairs)


def _normalize(value: str) -> str:
    return value.strip().lower()


def _matches_query(query: str, haystacks: list[str | None]) -> bool:
    if not query:
        return True
    needle = _normalize(query)
    return any(needle in _normalize(v or "") for v in haystacks)


def _matches_multi(selected: list[str], value: str) -> bool:
    if not selected:
        return True
    norm = _normalize(value)
    return any(_normalize(s) == norm for s in selected)


def _date_overlaps(
    start: str | None, end: str | None, from_date: str, to_date: str
) -> bool:
    if not from_date and not to_date:
        return True
    if not start or not end:
        return False
    try:
        item_start = date.fromisoformat(start)
        item_end = date.fromisoformat(end)
    except ValueError:
        return False

    filter_start = date.fromisoformat(from_date) if from_date else date.min
    filter_end = date.fromisoformat(to_date) if to_date else date.max
    return item_start <= filter_end and item_end >= filter_start


def _matches_upcoming(
    is_upcoming: bool, start: str | None, end: str | None, upcoming_only: bool
) -> bool:
    if not upcoming_only:
        return True
    if is_upcoming:
        return True
    if not start or not end:
        return False
    try:
        return date.fromisoformat(end) >= today_utc()
    except ValueError:
        return False


def apply_restaurant_filters(
    restaurants: list[Restaurant], filters: RestaurantFilters
) -> list[Restaurant]:
    return [
        r
        for r in restaurants
        if _matches_query(filters.query, [r.name, r.neighborhood, r.cuisine, r.address])
        and _matches_multi(filters.neighborhoods, r.neighborhood)
        and _matches_multi(filters.cuisines, r.cuisine)
        and _matches_upcoming(
            r.is_upcoming, r.opened_start_date, r.opened_end_date, filters.upcoming_only
        )
        and _date_overlaps(
            r.opened_start_date, r.opened_end_date, filters.from_date, filters.to_date
        )
    ]


def apply_event_filters(events: list[SFEvent], filters: EventFilters) -> list[SFEvent]:
    return [
        e
        for e in events
        if _matches_query(
            filters.query, [e.title, e.location, e.description, derive_event_category(e)]
        )
        and _matches_multi(filters.neighborhoods, derive_event_neighborhood(e))
        and _matches_multi(filters.categories, derive_event_category(e))
        and _matches_upcoming(
            e.is_upcoming, e.start_date, e.end_date, filters.upcoming_only
        )
        and _date_overlaps(e.start_date, e.end_date, filters.from_date, filters.to_date)
    ]
