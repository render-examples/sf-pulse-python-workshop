# Demo prompt: Add the events panel to SF Pulse (Python)

Follow the instructions in this file.

## What you are building

SF Pulse is a FastAPI + asyncpg + Render Workflows app that currently tracks SF restaurant openings. Your task is to implement a full events feature as a new addition to the app. The database migrations are already defined in `migrations/` and include the `events` table — run `uv run python -m bin.migrate` to apply them.

When you are done, the home page should have two tabs — Restaurants and Events — and the events table should show Mission District events from the database with realtime SSE updates, client-side filtering, and neighborhood-aware push notification preferences.

---

## Database schema (apply with `uv run python -m bin.migrate`)

```sql
-- events table (created by migrations 0001 + 0003 + 0007)
CREATE TABLE events (
  id            SERIAL PRIMARY KEY,
  title         TEXT        NOT NULL,
  location      TEXT        NOT NULL,
  date          TEXT        NOT NULL,
  time          TEXT,
  description   TEXT,
  source_url    TEXT,
  added_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  start_date    DATE,
  end_date      DATE,
  date_precision TEXT       NOT NULL DEFAULT 'unknown',
  is_upcoming   BOOLEAN     NOT NULL DEFAULT FALSE,
  dedupe_key    TEXT        NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS events_start_date_idx ON events (start_date);

-- push_subscriptions.preferences stores event_categories: list[str]
-- (normalized by normalize_push_preferences in app/shared/catalog.py)
```

The `dedupe_key` is computed as:

```
lower(title) | lower(location) | lower(date)
```

using `normalize_date_text(date)` for the date part.

---

## Pydantic types / dataclasses to add

### `app/shared/types.py`

Add the `SFEvent` model, `EventCategory` literal, an `events` field on `InitialData`, and `event_categories` field on `PushPreferences`:

```python
from typing import Literal

EventCategory = Literal["art", "community", "festival", "film", "market", "music"]


class SFEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    location: str
    date: str
    start_date: str | None = None
    end_date: str | None = None
    date_precision: DatePrecision
    is_upcoming: bool
    dedupe_key: str
    time: str | None = None
    description: str | None = None
    source_url: str | None = None


# Update InitialData:
class InitialData(BaseModel):
    restaurants: list[Restaurant]
    events: list[SFEvent]                                    # add this
    last_updated: str | None = Field(default=None, alias="lastUpdated")


# Update PushPreferences:
class PushPreferences(BaseModel):
    neighborhoods: list[str] = Field(default_factory=list)
    cuisines: list[str] = Field(default_factory=list)
    event_categories: list[str] = Field(default_factory=list)  # add this
```

### `app/storage.py`

Add `StoredEvent` (Pydantic) and `NewEvent` (dataclass):

```python
class StoredEvent(BaseModel):
    id: int
    title: str
    location: str
    date: str
    start_date: str | None = None
    end_date: str | None = None
    date_precision: DatePrecision
    is_upcoming: bool
    dedupe_key: str
    time: str | None = None
    description: str | None = None
    source_url: str | None = None
    added_at: datetime


@dataclass
class NewEvent:
    title: str
    location: str
    date: str
    time: str | None = None
    description: str | None = None
    source_url: str | None = None
```

### `app/llm/schemas.py`

Add the `ExtractedEvent` and `EventExtraction` schemas:

```python
class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    location: str
    date: str
    time: str | None = None
    description: str | None = None


class EventExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: list[ExtractedEvent] = Field(default_factory=list)
```

---

## Files to create

### `app/shared/identity.py` (extend)

Add `build_event_identity_key`:

```python
def build_event_identity_key(*, title: str, location: str, date_text: str) -> str:
    return "|".join(
        [_normalize_part(title), _normalize_part(location), _normalize_part(date_text)]
    )
```

### `app/routes/api_events.py`

```python
"""Event API routes."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app import storage
from app.routes.utils import require_cron_secret
from app.sse import broadcast

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def list_events() -> list[storage.StoredEvent]:
    return await storage.get_visible_events()


@router.get("/events/{id}")
async def get_event(id: int) -> storage.StoredEvent:
    row = await storage.get_event_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return row


@router.delete("/events/{id}", dependencies=[Depends(require_cron_secret)])
async def delete_event(id: int) -> dict:
    existing = await storage.get_event_by_id(id)
    await storage.delete_event(id)

    version: str | None = None
    if existing:
        update = await storage.record_update("event", existing.title, "removed")
        version = update.occurred_at.isoformat()

    await broadcast(
        "events",
        {
            "version": version,
            "upserted": [],
            "deleted": [id],
            "summary": f"Removed event: {existing.title}" if existing else None,
        },
    )
    return {"ok": True}
```

Then wire it into `app/main.py`:

```python
from app.routes import (
    api_events,           # add
    api_health,
    ...
)
...
app.include_router(api_events.router)  # add after api_restaurants
```

### `app/templates/event_detail.html`

Mirror `app/templates/restaurant_detail.html` structure. Render:
- Event title in `<h1>`
- Category badge using `format_event_category(category)`
- Neighborhood badge using `derive_event_neighborhood(event)`
- Date / time / location / description
- Source link button + Google Maps link (`map_query` context var)
- "Tracked metadata" section (`start_date`, `end_date`, `is_upcoming`, `date_precision`, `dedupe_key`)
- "Related events" section: events in same neighborhood
- "Nearby restaurants" section: restaurants in same neighborhood
- A `← Back to events` link to `/#events`

### `app/sources/funcheap.py`

Funcheap RSS scraper. Returns `list[NewEvent]`.

```python
async def fetch_funcheap_events() -> list[storage.NewEvent]:
    """Fetch SF Funcheap RSS, parse <item> tags, normalize dates from titles
    like 'Event Name (April 5, 2026)'. Filter items older than ~60 days.
    Skip generic / search-like titles. Each result: title, location, date,
    description, source_url=item.link.
    """
```

URL: `https://sf.funcheap.com/feed/`.

Helper: `normalize_funcheap_title_and_date(title, date_text)` strips the embedded date from titles and uses it to override the RSS pubDate when more specific.

### `app/sources/famsf.py`

Fine Arts Museums of SF calendar scraper using selectolax.

```python
async def fetch_famsf_events() -> list[storage.NewEvent]:
    """Fetch https://www.famsf.org/visit/calendar, parse event cards
    (heading paired with date range), set location to 'de Young Museum' or
    'Legion of Honor'. Skip generic / repeated nav titles.
    Each result: title, location, date, source_url=https://www.famsf.org/visit/calendar.
    """
```

Expose a private `parse_museum_events(html, source_url, default_location)` so Cal Academy can reuse it.

### `app/sources/cal_academy.py`

```python
from app.sources.famsf import parse_museum_events


async def fetch_cal_academy_events() -> list[storage.NewEvent]:
    """Fetch https://www.calacademy.org/events, reuse parse_museum_events
    with location='California Academy of Sciences'.
    """
```

### `app/sources/ddg_search.py` (extend)

Add:

```python
async def search_events_ddg() -> list[RawArticle]:
    """Run the canonical 'San Francisco events Golden Gate Park concerts {Month Year}' query.
    Returns one RawArticle whose body_text is the stripped DDG result page,
    consumed by extract_events_from_articles in the LLM path.
    """
    month_year = _month_year()
    html = await ddg_search(
        f"San Francisco events Golden Gate Park concerts {month_year}"
    )
    return [
        RawArticle(
            source="ddg",
            url="",
            title=f"DDG: San Francisco events {month_year}",
            pubDate=None,
            bodyText=extract_body_text(html) if html else "",
        )
    ]
```

### `workflow/tasks/fetch_funcheap.py`

```python
from __future__ import annotations

import logging

from render_sdk import Retry

from app.sources.funcheap import fetch_funcheap_events
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="fetch-funcheap",
    retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2),
    timeout_seconds=120,
)
async def fetch_funcheap() -> list[dict]:
    logger.info("[workflow] fetching Funcheap...")
    events = await fetch_funcheap_events()
    logger.info("[workflow] Funcheap: %d events", len(events))
    from dataclasses import asdict
    return [asdict(e) for e in events]
```

### `workflow/tasks/fetch_famsf.py`

Same pattern, calls `fetch_famsf_events()`.

### `workflow/tasks/fetch_cal_academy.py`

Same pattern, calls `fetch_cal_academy_events()`.

### `workflow/tasks/search_events.py`

```python
from __future__ import annotations

import logging

from render_sdk import Retry

from app.sources.ddg_search import search_events_ddg
from workflow._app import app

logger = logging.getLogger(__name__)


@app.task(
    name="search-events",
    retry=Retry(max_retries=2, wait_duration_ms=3000, backoff_scaling=2),
    timeout_seconds=90,
)
async def search_events() -> list[dict]:
    logger.info("[workflow] DDG event search...")
    articles = await search_events_ddg()
    logger.info("[workflow] DDG events: %d articles", len(articles))
    return [a.model_dump(by_alias=True, mode="json") for a in articles]
```

### `tests/test_api_events.py`

Integration tests for `GET /api/events`, `GET /api/events/{id}`, `DELETE /api/events/{id}`. Follow the same pattern as `tests/test_api_restaurants.py` — use the `client` and `clean_db` fixtures from `conftest.py`, seed events via `storage.add_event(...)`, and assert delete requires `x-cron-secret`.

---

## Files to modify

### `app/shared/catalog.py`

Add event category constants, derivation, and push-preference matching:

```python
EVENT_CATEGORY_LABELS: dict[EventCategory, str] = {
    "art": "Art",
    "community": "Community",
    "festival": "Festival",
    "film": "Film",
    "market": "Market",
    "music": "Music",
}


def format_event_category(category: EventCategory) -> str:
    return EVENT_CATEGORY_LABELS[category]


_RE_MARKET = re.compile(r"(night market|market\b|vendor|craft fair)", re.IGNORECASE)
_RE_FILM = re.compile(r"(film|screening|roxie|cinema|theater|theatre|4k)", re.IGNORECASE)
_RE_MUSIC = re.compile(r"(concert|live music|music hall|goldenvoice|popscene|dj\b|album release|band\b|tour\b)", re.IGNORECASE)
_RE_FESTIVAL = re.compile(r"(festival|parade|carnaval|celebration|fair\b|holiday)", re.IGNORECASE)
_RE_ART = re.compile(r"(art\b|poetry|gallery|performance project|installation)", re.IGNORECASE)


def derive_event_category(event: SFEvent | dict) -> EventCategory:
    title, location, description = (
        (event.title, event.location, event.description or "")
        if isinstance(event, SFEvent)
        else (event.get("title", ""), event.get("location", ""), event.get("description") or "")
    )
    haystack = f"{title} {location} {description}".lower()

    if _RE_MARKET.search(haystack):   return "market"
    if _RE_FILM.search(haystack):     return "film"
    if _RE_MUSIC.search(haystack):    return "music"
    if _RE_FESTIVAL.search(haystack): return "festival"
    if _RE_ART.search(haystack):      return "art"
    return "community"


def derive_event_neighborhood(event: SFEvent | dict) -> str:
    location = event.location if isinstance(event, SFEvent) else event.get("location", "")
    for alias in NEIGHBORHOOD_ALIASES:
        if any(p.search(location) for p in alias.patterns):
            return alias.label
    return "Other SF"


def get_event_neighborhood_options(events: list[SFEvent]) -> list[str]:
    return _unique_sorted([derive_event_neighborhood(e) for e in events])


def get_event_category_options(events: list[SFEvent]) -> list[EventCategory]:
    cats = _unique_sorted([derive_event_category(e) for e in events])
    return [c for c in cats if c in EVENT_CATEGORY_LABELS]  # type: ignore[misc]


def matches_preferred_event_category(category: EventCategory, prefs: PushPreferences) -> bool:
    if not prefs.event_categories:
        return True
    return category in prefs.event_categories


def event_matches_push_preferences(event: SFEvent, prefs: PushPreferences) -> bool:
    return matches_preferred_neighborhood(
        derive_event_neighborhood(event), prefs
    ) and matches_preferred_event_category(derive_event_category(event), prefs)
```

Update `normalize_push_preferences` to include `event_categories`:

```python
categories = [
    v
    for v in _unique_sorted([str(v).strip() for v in (prefs_dict.get("event_categories") or [])])
    if v in EVENT_CATEGORY_LABELS
]
return PushPreferences(neighborhoods=neighborhoods, cuisines=cuisines, event_categories=categories)
```

Update `has_push_preferences` to include `event_categories`:

```python
return bool(prefs.neighborhoods or prefs.cuisines or prefs.event_categories)
```

Update `NeighborhoodGroup` and `group_by_neighborhood` to take an additional events list and bucket events into the same group dict.

### `app/shared/filters.py`

Add `EventFilters`, `DEFAULT_EVENT_FILTERS`, `events` key on `HomeFilters`, `apply_event_filters`, and `e-*` URL params:

```python
@dataclass
class EventFilters:
    query: str = ""
    neighborhoods: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    upcoming_only: bool = False
    from_date: str = ""
    to_date: str = ""


DEFAULT_EVENT_FILTERS = EventFilters()


@dataclass
class HomeFilters:
    restaurants: RestaurantFilters = field(default_factory=RestaurantFilters)
    events: EventFilters = field(default_factory=EventFilters)
```

`parse_home_filters` reads `e-q`, `e-neighborhood`, `e-category`, `e-upcoming` (== "1"), `e-from`, `e-to`.
`serialize_home_filters` writes the same keys.

```python
def apply_event_filters(events: list[SFEvent], filters: EventFilters) -> list[SFEvent]:
    return [
        e
        for e in events
        if _matches_query(
            filters.query, [e.title, e.location, e.description, derive_event_category(e)]
        )
        and _matches_multi(filters.neighborhoods, derive_event_neighborhood(e))
        and _matches_multi(filters.categories, derive_event_category(e))
        and _matches_upcoming(e.is_upcoming, e.start_date, e.end_date, filters.upcoming_only)
        and _date_overlaps(e.start_date, e.end_date, filters.from_date, filters.to_date)
    ]
```

### `app/storage.py`

Add storage helpers (all accept optional `pool` kwarg, use parameterized SQL):

- `_row_to_event(row)` — mirror `_row_to_restaurant`. Derives `start_date`, `end_date`, `date_precision`, `is_upcoming` via `derive_structured_date(date)`. Backfills `dedupe_key` if missing using `build_event_identity_key`.
- `get_events()` — `SELECT * FROM events`, sort by `compare_date_text(a.date, b.date)`.
- `get_visible_events()` — same as `get_events()` (visibility is determined by date, not a SQL filter).
- `add_event(e: NewEvent)` — `INSERT … ON CONFLICT (dedupe_key) DO UPDATE` (upsert). Compute `dedupe_key` via `build_event_identity_key`. Compute structured dates via `derive_structured_date`.
- `update_event(id, e: NewEvent)` — `UPDATE` by id, recompute dedupe_key + structured dates.
- `get_event_by_dedupe_key(key)` — `SELECT … WHERE dedupe_key = $1`.
- `get_event_by_id(id)` — `SELECT … WHERE id = $1`.
- `clear_events()` — `DELETE FROM events`.
- `delete_event(id)` — `DELETE FROM events WHERE id = $1`.

Update the `UpdateType` Literal to include `"event"`:

```python
UpdateType = Literal["restaurant", "event"]
```

### `app/refresh.py`

Add event processing to `apply_discovered_items`:

- Add `events: Iterable[NewEvent] = ()` param.
- `ApplyDiscoveredItemsResult` gets `added_events: list[str]`, `updated_events: list[str]`.
- Add `_find_matching_event`, `_merge_event`, `_event_changed`, `_build_event_source_match_key`.
- Add an event processing loop mirroring the restaurant loop.
- After the restaurant `broadcast("restaurants", ...)`, also `broadcast("events", { version, upserted, deleted: [], summary })` if any events were added/updated.
- Update `_push_to_interested` to accept `events: list[StoredEvent]`. Use `event_matches_push_preferences`.
- Update `_build_push_payload` to handle the `events.length == 1 and not restaurants` single-event case.
- Add `dedup_events()`:

```python
def dedup_events(items: list[storage.NewEvent]) -> list[storage.NewEvent]:
    seen: set[str] = set()
    out: list[storage.NewEvent] = []
    for e in items:
        key = build_event_identity_key(title=e.title, location=e.location, date_text=e.date)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
```

Key `_merge_event` rules:
- Title: prefer longer (more descriptive)
- Location: prefer non-generic (avoid "San Francisco" generic)
- Date: prefer more precise (`_prefers_incoming_date`)
- Description: prefer longer with higher "score" — discount Funcheap's `appeared first on funcheap` footer
- time, source_url: incoming ?? existing ?? null

Key `_find_matching_event` rules:
1. Exact `dedupe_key` match
2. `_build_event_source_match_key` = `source_url + "|" + normalized_title + "|" + normalized_date` (only if source_url present)
3. Fuzzy: same normalized title + same normalized date + same/generic location

Update `run_daily_refresh` to fetch events sources too:

```python
funcheap_raw, famsf_raw, cal_academy_raw, ddg_e_raw = await asyncio.gather(
    fetch_funcheap_events(),
    fetch_famsf_events(),
    fetch_cal_academy_events(),
    search_events_ddg(),
    return_exceptions=True,
)
...
events = dedup_events([*funcheap_events, *famsf_events, *cal_academy_events, *llm_events])
if restaurants or events:
    await apply_discovered_items(restaurants=restaurants, events=events, pool=pool)
return {"restaurants": len(restaurants), "events": len(events)}
```

### `app/llm/pipeline.py`

Add `extract_events_from_articles`:

```python
async def extract_events_from_articles(
    client: LLMClient, articles: list[RawArticle]
) -> list[NewEvent]:
    if not articles:
        return []

    results: list[NewEvent] = []
    for batch in _batch_articles(articles):
        source_url = batch[0].url if len(batch) == 1 else None
        extraction = await extract_structured(
            client,
            schema=EventExtraction,
            prompt=EVENT_EXTRACTION_PROMPT,
            text=_format_article_batch(batch),
        )
        if extraction is None:
            continue
        for e in extraction.events:
            results.append(
                NewEvent(
                    title=e.title,
                    location=e.location,
                    date=e.date,
                    time=e.time,
                    description=e.description,
                    source_url=source_url,
                )
            )
    return results
```

### `app/llm/schemas.py`

Add the `EVENT_EXTRACTION_PROMPT` (full text):

```python
EVENT_EXTRACTION_PROMPT = """You extract information about events happening in San Francisco from article text.

Rules:
- Extract events happening in San Francisco or the immediate Bay Area venues (Golden Gate Park, Fort Mason, Yerba Buena, etc.).
- "title": use the specific event name, not generic categories like "Concert" or "Festival".
- "location": use the venue name (e.g. "Golden Gate Park", "de Young Museum"), not the full street address.
- "date": use the most specific format available. For single dates: "April 23, 2026". For ranges: "April 23 - 25, 2026".
- "time": if mentioned, use "7:30 PM - 11:00 PM" format. Use null if no time is specified.
- "description": 1-2 sentence summary of the event. Remove boilerplate, promotional language, and ticket/pricing info. Use null if no meaningful description is available.
- Skip recurring/generic listings that don't have a specific date.
- Skip events that are clearly not in the San Francisco area.
- If multiple articles are provided (delimited by <article> tags), extract events from all of them.
- Return an empty array if no qualifying events are found."""
```

### `app/llm/__init__.py`

Re-export the new symbols:

```python
from app.llm.pipeline import (
    extract_events_from_articles,
    extract_restaurants_from_articles,
)
from app.llm.schemas import (
    EVENT_EXTRACTION_PROMPT,
    RESTAURANT_EXTRACTION_PROMPT,
    EventExtraction,
    RawArticle,
    RestaurantExtraction,
)
```

Add `EVENT_EXTRACTION_PROMPT`, `EventExtraction`, `extract_events_from_articles` to `__all__`.

### `app/security.py`

Add `VALID_EVENT_CATEGORIES` and an `event_categories` field on `PushPreferencesPayload` with category validation:

```python
VALID_EVENT_CATEGORIES: set[str] = {"art", "community", "festival", "film", "market", "music"}


class PushPreferencesPayload(BaseModel):
    model_config = {"extra": "forbid"}
    neighborhoods: list[str] = Field(default_factory=list)
    cuisines: list[str] = Field(default_factory=list)
    event_categories: list[str] = Field(default_factory=list)

    @field_validator("event_categories")
    @classmethod
    def _categories_valid(cls, value: list[str]) -> list[str]:
        for v in value:
            if v not in VALID_EVENT_CATEGORIES:
                raise ValueError(f"invalid event category: {v}")
        return value

    # ... existing validators ...
```

Re-export `EventCategory` from the module's `__all__`.

### `app/routes/utils.py`

Extend `get_initial_data()` to fetch events alongside restaurants in the same `gather`:

```python
async def get_initial_data() -> InitialData:
    restaurants_task = asyncio.create_task(storage.get_visible_restaurants())
    events_task = asyncio.create_task(storage.get_visible_events())
    updates_task = asyncio.create_task(storage.get_recent_updates(1))
    restaurants, events, updates = await asyncio.gather(
        restaurants_task, events_task, updates_task
    )
    last_updated = updates[0].occurred_at.isoformat() if updates else None
    return InitialData(
        restaurants=[Restaurant.model_validate(r.model_dump()) for r in restaurants],
        events=[SFEvent.model_validate(e.model_dump()) for e in events],
        lastUpdated=last_updated,
    )
```

### `app/routes/pages.py`

Add the `/events/{id}` route, register category/neighborhood derivation as Jinja globals:

```python
templates.env.globals.update(
    derive_event_category=derive_event_category,
    derive_event_neighborhood=derive_event_neighborhood,
    format_event_category=format_event_category,
    build_timeline=build_timeline,
)


@router.get("/events/{id}", response_class=HTMLResponse)
async def event_detail(id: int, request: Request) -> HTMLResponse:
    row = await storage.get_event_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event_public = SFEvent.model_validate(row.model_dump())
    category = derive_event_category(event_public)
    neighborhood = derive_event_neighborhood(event_public)
    visible_events = [
        SFEvent.model_validate(e.model_dump())
        for e in await storage.get_visible_events()
    ]
    visible_restaurants = await storage.get_visible_restaurants()
    related_events = [
        item for item in visible_events
        if item.id != row.id and derive_event_neighborhood(item) == neighborhood
    ][:5]
    related_restaurants = [
        r for r in visible_restaurants if r.neighborhood == neighborhood
    ][:5]
    map_query = (
        f"https://www.google.com/maps/search/?api=1&query={quote(row.location)}"
        if row.location else None
    )
    return templates.TemplateResponse(
        request, "event_detail.html",
        {
            "title": f"{row.title} — SF Pulse",
            "event": row,
            "category": category,
            "category_label": format_event_category(category),
            "neighborhood": neighborhood,
            "related_events": related_events,
            "related_restaurants": related_restaurants,
            "map_query": map_query,
        },
    )
```

Update the `home` route to pass `events`, `event_neighborhoods`, and `event_categories` to the template.

Update the `restaurant_detail` route to compute `nearby_events`:

```python
nearby_events = [
    event for event in visible_events
    if derive_event_neighborhood(event) == row.neighborhood
][:5]
```

…and pass `nearby_events` to the template.

### `app/templates/base.html`

Update meta description to include events:

```html
<meta name="description" content="Track new San Francisco restaurant openings and upcoming local events. Updated daily." />
```

### `app/templates/index.html`

Update site subtitle: `"New restaurants & local events"`.

Add an Events tab:

```html
<a class="tab tabEvents" href="#events" data-tab="events">
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
    <line x1="16" y1="2" x2="16" y2="6"></line>
    <line x1="8" y1="2" x2="8" y2="6"></line>
    <line x1="3" y1="10" x2="21" y2="10"></line>
  </svg>
  Events ({{ events|length }})
</a>
```

Add the events panel section (after the restaurants `<section>`, before `<section id="diagram">`):

```html
<section id="events" class="panel" hidden>
  <table class="dataTable">
    <thead>
      <tr><th>Title</th><th>Neighborhood</th><th>Category</th><th>Time</th><th>Date</th></tr>
    </thead>
    <tbody data-table="events">
      {% for e in events %}
      <tr data-row-id="{{ e.id }}">
        <td>
          <div class="cellPrimary"><a class="detailLink" href="/events/{{ e.id }}">{{ e.title }}</a></div>
          {% if e.location %}<div class="cellSub cellAddress">{{ e.location }}</div>{% endif %}
          {% if e.description %}<div class="cellSub eventDescription">{{ e.description }}</div>{% endif %}
          {% if e.source_url %}<a href="{{ e.source_url }}" target="_blank" rel="noopener noreferrer" class="cellSource">Source</a>{% endif %}
        </td>
        <td><span class="badge">{{ derive_event_neighborhood(e) }}</span></td>
        <td class="tableMuted">{{ format_event_category(derive_event_category(e)) }}</td>
        <td class="tableMuted tableDate">{{ e.time or "—" }}</td>
        <td class="tableMuted tableDate">{{ e.date }}</td>
      </tr>
      {% else %}
      <tr><td colspan="5" class="emptyCell">No events yet — check back after the next refresh.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
```

### `app/templates/restaurant_detail.html`

Add a "Nearby events" section (above "Related restaurants"):

```html
<section class="detailSection">
  <h2 class="detailSectionTitle">Nearby events</h2>
  {% if nearby_events %}
  <ul class="detailList">
    {% for event in nearby_events %}
    <li class="detailListItem">
      <a href="/events/{{ event.id }}">{{ event.title }}</a>
      <span class="detailListMeta">{{ event.date }}</span>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="detailListMeta">No related nearby events are currently tracked.</p>
  {% endif %}
</section>
```

Update the fallback hero summary copy:

```jinja2
SF Pulse detail page with opening date, neighborhood, source links, and nearby events.
```

### `app/templates/map.html`

Show event count alongside restaurant count:

```html
<p class="meta">{{ restaurants|length }} restaurants and {{ events|length }} events plotted by neighborhood.</p>
```

### `static/styles/home.css`

Re-introduce the events tab/section toggling. **Use a class on `.page`, not `:has(#events:target)`** — `:has()` triggers a full style recalculation on every hash change, which causes a perceptible delay when switching tabs.

Add tab toggle logic:

```css
/* .eventsActive is toggled by home.js on click/load (see syncTabClass).
   Do NOT use :has(#events:target) — it forces a full style recalculation
   on every hash change, causing a perceptible delay. */
.eventsSection,
.diagramSection {
  display: none;
}

.page:has(#diagram:target) .restaurantsSection {
  display: none;
}
.page.eventsActive .restaurantsSection { display: none; }
.page.eventsActive .eventsSection { display: grid; }
```

Add the `.eventsSection` layout (mirror `.restaurantsSection`) and the `.colTime` column (`width: 80px`; hide below tablet breakpoint).

Add event-description expand/collapse CSS:

```css
.eventDescription { max-width: 60ch; }
.eventDescriptionText { display: block; overflow: hidden; line-height: 1.35; transition: max-height 150ms ease; }
.eventDescription[data-clamp-ready="true"] .eventDescriptionText {
  max-height: var(--event-description-expanded-height);
}
.eventDescription[data-clamp-ready="true"][data-expanded="false"] .eventDescriptionText {
  max-height: var(--event-description-collapsed-height);
}
.eventDescription[data-expanded="false"]:not([data-animating="true"]) .eventDescriptionText {
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3;
}
.eventDescriptionToggle { color: var(--accent); font-size: 12px; font-weight: 600; line-height: 1.3; margin-top: 2px; }
.eventDescriptionToggle:hover { text-decoration: underline; }
@media (prefers-reduced-motion: reduce) { .eventDescriptionText { transition: none; } }
```

### `static/home.js`

Add events handling:

1. Include `'events'` in the panel-routing whitelist:

```js
showPanel(['restaurants', 'events', 'diagram'].includes(hash) ? hash : 'restaurants')
```

2. Add an SSE listener for `events`:

```js
source.addEventListener('events', (ev) => onCollectionUpdate('events', ev))
```

3. (Optional but recommended for polish) implement event-description expand/collapse with **double-`requestAnimationFrame`**: the outer rAF lets the browser paint (making the section visible), the inner rAF measures `scrollHeight` after layout is computed. A single rAF runs before paint and forces a full layout of the newly-visible table, causing a ~1 s freeze. **Batch all reads into one loop, then writes into a second loop** — interleaving them causes layout thrashing (one reflow per row).

### `static/map.js`

Restore the events branch:

```js
const [restaurants, events] = await Promise.all([
  fetch('/api/restaurants').then((r) => r.json()),
  fetch('/api/events').then((r) => r.json()),
])
// ... bucket events into groups, render counts ...
```

### `workflow/main.py` and `workflow/tasks/__init__.py`

Re-add imports for the four new tasks (`fetch_funcheap`, `fetch_famsf`, `fetch_cal_academy`, `search_events`) and re-export them in `__all__`.

### `workflow/tasks/daily_refresh.py`

Re-add the event fan-out alongside the existing restaurant phase:

```python
funcheap_raw, famsf_raw, cal_academy_raw, ddg_e_raw = await asyncio.gather(
    fetch_funcheap(),
    fetch_famsf(),
    fetch_cal_academy(),
    search_events(),
    return_exceptions=True,
)

funcheap_events = _to_new_events(_settled(funcheap_raw, "Funcheap", []))
famsf_events = _to_new_events(_settled(famsf_raw, "FAMSF", []))
cal_academy_events = _to_new_events(_settled(cal_academy_raw, "Cal Academy", []))
ddg_event_articles = _to_raw_articles(_settled(ddg_e_raw, "DDG events", []))

# LLM extraction:
if llm is not None:
    e_results = await asyncio.gather(
        extract_events_from_articles(llm, ddg_event_articles),
        return_exceptions=True,
    )
    for e in e_results:
        llm_events.extend(_settled(e, "LLM events", []))

events = dedup_events([*funcheap_events, *famsf_events, *cal_academy_events, *llm_events])

if restaurants or events:
    await apply_discovered_items(
        restaurants=[asdict(r) for r in restaurants],
        events=[asdict(e) for e in events],
    )
return {"restaurants": len(restaurants), "events": len(events)}
```

Add the `_to_new_events` helper:

```python
def _to_new_events(items: Any) -> list[NewEvent]:
    return [NewEvent(**item) for item in _coerce_list(items)]
```

### `workflow/tasks/apply_discovered_items.py`

Accept and pass `events`:

```python
async def apply_discovered_items(
    restaurants: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    restaurant_objs = [NewRestaurant(**r) for r in (restaurants or [])]
    event_objs = [NewEvent(**e) for e in (events or [])]
    result = await refresh_apply_discovered_items(
        restaurants=restaurant_objs, events=event_objs,
    )
    return {
        "added_restaurants": list(result.added_restaurants),
        "updated_restaurants": list(result.updated_restaurants),
        "added_events": list(result.added_events),
        "updated_events": list(result.updated_events),
    }
```

### `AGENTS.md`

Update to reflect that the app now tracks both restaurants and events:

- Heading: `"It tracks SF restaurant openings and local events."`
- Storage layer blurb: `"ON CONFLICT upserts use identity_key (restaurants) and dedupe_key (events) to prevent duplicates."`

---

## Crawler sources

### Funcheap RSS (`fetch_funcheap_events`)

- Fetch RSS from `https://sf.funcheap.com/feed/`.
- Parse `<item>` tags: `<title>`, `<link>`, `<pubDate>`, `<description>` (HTML — strip tags).
- Apply `normalize_funcheap_title_and_date(title, date)` to extract embedded dates from titles like `"Event Name (April 5, 2026)"`.
- Filter: skip items older than ~60 days from today; skip items with generic / search-like titles.
- Each `NewEvent`: `title`, `location` (often `"San Francisco"` if not in description), `date`, `description`, `source_url=item.link`.

### FAMSF calendar (`fetch_famsf_events`)

- Fetch HTML from `https://www.famsf.org/visit/calendar`.
- Parse event cards: title, date range, location (`de Young Museum` or `Legion of Honor`).
- Skip generic/repeated navigation titles.
- Each `NewEvent`: `title`, `location`, `date`, `source_url="https://www.famsf.org/visit/calendar"`.

### Cal Academy events (`fetch_cal_academy_events`)

- Fetch HTML from `https://www.calacademy.org/events`.
- Reuse `parse_museum_events()` from `funcheap.py` / `famsf.py`.
- `source_url="https://www.calacademy.org/events"`, `location="California Academy of Sciences"`.

### DuckDuckGo fallback (`search_events_ddg`)

- Search DDG for `"San Francisco events Golden Gate Park concerts {Month Year}"`.
- Extract article URLs from results, fetch top 3 full article pages.
- Return `list[RawArticle]` (`title`, `url`, `body_text`) — consumed by `extract_events_from_articles` in the LLM path; not parsed directly into events.

---

## Deduplication (`dedup_events`)

Before passing events to `apply_discovered_items`, dedup the merged list from all sources:

```python
def dedup_events(items: list[NewEvent]) -> list[NewEvent]:
    seen: set[str] = set()
    out: list[NewEvent] = []
    for e in items:
        key = build_event_identity_key(
            title=e.title, location=e.location, date_text=normalize_date_text(e.date)
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
```

---

## Architecture patterns to follow

- **Storage functions** accept `pool: asyncpg.Pool | None = None` as a kwarg. Default pool comes from `app.db.get_pool()`. ON CONFLICT upserts use `dedupe_key` for events.
- **SSR via Jinja2**: server data is fetched in route handlers and passed as the template context. Tables are rendered server-side from the `events` list.
- **Client-side filter state** lives in URL params: `r-*` for restaurants, `e-*` for events (`e-q`, `e-neighborhood`, `e-category`, `e-upcoming`, `e-from`, `e-to`).
- **SSE deltas** are named `"events"` (same channel pattern as `"restaurants"`). Each delta is `{ version, upserted: list[StoredEvent], deleted: list[int], summary?: str }`. The `/api/events-stream` endpoint already exists — agents only need to broadcast through `app.sse.broadcast(...)`.
- **Push preferences** — `event_categories` is normalized by `normalize_push_preferences` (drop unknown values via the same set-membership filter pattern). Preferences are stored as JSONB in `push_subscriptions.preferences`.
- **LLM extraction** — `EventExtraction` and `EVENT_EXTRACTION_PROMPT` are defined in `app/llm/schemas.py`. Use them via `extract_structured(client, schema=..., prompt=..., text=...)`.
- **Blocked-name pattern** — events do **not** have a block list (unlike restaurants). Insert all non-generic events.
- **`normalize_date_text`** lives in `app/shared/dates.py`. Use it for consistent date normalization before building dedupe keys.

---

## Verification steps

After implementing all the above:

1. `uv run pyright` — zero errors.
2. `uv run ruff check` — zero errors.
3. `uv run pytest -q` — all tests pass (including new `tests/test_api_events.py`).
4. `uv run python -m bin.migrate` — migrations apply cleanly.
5. `uv run uvicorn app.main:app --reload` — visit `http://localhost:8000`:
   - Home page shows two tabs: Restaurants and Events.
   - Clicking "Events" tab switches to the events section.
   - Events table renders rows from the database (seed data has 20+ Mission District events).
   - Filtering by title keyword narrows the events list.
   - `/events/1` renders the event detail page.
   - `/api/events` returns a JSON array of events.
6. Spot-check push preferences: click the bell icon, open preferences, verify "Event categories" checkboxes appear and can be saved (sends `event_categories: list[str]`, server validates via `VALID_EVENT_CATEGORIES`).
7. Run `uv run python -c "import asyncio; from app.refresh import run_daily_refresh; asyncio.run(run_daily_refresh())"` (with or without `LLM_API_KEY`) — restaurants AND events are upserted.
