"""Data access layer — port of server/storage.ts.

All queries use parameterized statements via asyncpg. Functions accept an
optional Pool (for tests/test injection); otherwise they use the singleton
pool from app.db.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, TypedDict

import asyncpg
from pydantic import BaseModel

from app.db import get_pool
from app.shared.catalog import normalize_push_preferences
from app.shared.dates import DatePrecision, derive_structured_date, today_utc
from app.shared.identity import build_restaurant_identity_key
from app.shared.types import HighlightKind, PushPreferences


class PushKeys(TypedDict):
    p256dh: str
    auth: str


class StoredRestaurant(BaseModel):
    id: int
    name: str
    neighborhood: str
    cuisine: str
    address: str | None = None
    opened_date: str
    opened_start_date: str | None = None
    opened_end_date: str | None = None
    opened_date_precision: DatePrecision
    is_upcoming: bool
    highlight_kind: HighlightKind = "opening"
    source_url: str | None = None
    added_at: datetime


class StoredPushSubscription(BaseModel):
    id: int
    endpoint: str
    keys: PushKeys
    preferences: PushPreferences
    created_at: datetime
    updated_at: datetime


class DataUpdate(BaseModel):
    id: int
    type: str
    item_name: str
    action: str
    occurred_at: datetime


class CronRun(BaseModel):
    job_name: str
    last_ran_at: datetime


@dataclass
class NewRestaurant:
    name: str
    neighborhood: str
    cuisine: str
    opened_date: str
    address: str | None = None
    source_url: str | None = None
    highlight_kind: HighlightKind = "opening"


# ── Pool helpers ───────────────────────────────────────────────────────────────


async def _pool_or_default(pool: asyncpg.Pool | None) -> asyncpg.Pool:
    return pool if pool is not None else await get_pool()


async def _fetch(sql: str, *params: Any, pool: asyncpg.Pool | None = None) -> list[asyncpg.Record]:
    p = await _pool_or_default(pool)
    return await p.fetch(sql, *params)


async def _fetchrow(
    sql: str, *params: Any, pool: asyncpg.Pool | None = None
) -> asyncpg.Record | None:
    p = await _pool_or_default(pool)
    return await p.fetchrow(sql, *params)


async def _execute(sql: str, *params: Any, pool: asyncpg.Pool | None = None) -> None:
    p = await _pool_or_default(pool)
    await p.execute(sql, *params)


# ── Normalisation helpers ──────────────────────────────────────────────────────


def _to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            return value
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return value
    return None


def _to_date(value: Any) -> date | None:
    # asyncpg requires real `date` objects for typed-`date` columns;
    # derive_structured_date() returns ISO strings, so coerce here.
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _row_to_restaurant(row: asyncpg.Record | dict) -> StoredRestaurant:
    data = dict(row)
    opened_start = _to_iso_date(data.get("opened_start_date"))
    opened_end = _to_iso_date(data.get("opened_end_date"))
    precision = data.get("opened_date_precision") or "unknown"
    is_upcoming = bool(data.get("is_upcoming"))

    if opened_start is None or opened_end is None or precision == "unknown":
        structured = derive_structured_date(data["opened_date"])
        opened_start = opened_start or structured.start_date
        opened_end = opened_end or structured.end_date
        if precision == "unknown":
            precision = structured.date_precision
        if opened_start is None and opened_end is None:
            is_upcoming = structured.is_upcoming

    data.update(
        opened_start_date=opened_start,
        opened_end_date=opened_end,
        opened_date_precision=precision,
        is_upcoming=is_upcoming,
    )
    return StoredRestaurant.model_validate(data)


def _row_to_subscription(row: asyncpg.Record | dict) -> StoredPushSubscription:
    data = dict(row)
    keys = data.get("keys")
    if isinstance(keys, str):
        keys = json.loads(keys)
    prefs = data.get("preferences")
    if isinstance(prefs, str):
        prefs = json.loads(prefs)
    data["keys"] = keys
    data["preferences"] = normalize_push_preferences(prefs).model_dump()
    return StoredPushSubscription.model_validate(data)


def _subtract_months(reference: date, months: int) -> date:
    months_total = reference.month - months
    year = reference.year + (months_total - 1) // 12
    month = (months_total - 1) % 12 + 1
    day = min(reference.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _is_visible_restaurant(r: StoredRestaurant, reference: date | None = None) -> bool:
    reference = reference or today_utc()
    if r.highlight_kind == "michelin":
        return True
    if r.is_upcoming:
        return True
    if not r.opened_start_date:
        return False
    cutoff = _subtract_months(reference, 3)
    return date.fromisoformat(r.opened_start_date) >= cutoff


# ── Restaurants ────────────────────────────────────────────────────────────────


async def get_restaurants(*, pool: asyncpg.Pool | None = None) -> list[StoredRestaurant]:
    rows = await _fetch("SELECT * FROM restaurants ORDER BY added_at DESC", pool=pool)
    return [_row_to_restaurant(r) for r in rows]


async def get_visible_restaurants(*, pool: asyncpg.Pool | None = None) -> list[StoredRestaurant]:
    cutoff = _subtract_months(today_utc(), 3)
    rows = await _fetch(
        """
        SELECT *
        FROM restaurants
        WHERE highlight_kind = 'michelin'
           OR is_upcoming = TRUE
           OR opened_start_date >= $1
           OR opened_start_date IS NULL
        ORDER BY added_at DESC
        """,
        cutoff,
        pool=pool,
    )
    items = [_row_to_restaurant(r) for r in rows]
    return [r for r in items if _is_visible_restaurant(r)]


async def add_restaurant(
    r: NewRestaurant, *, pool: asyncpg.Pool | None = None
) -> StoredRestaurant:
    structured = derive_structured_date(r.opened_date)
    identity_key = build_restaurant_identity_key(
        name=r.name, address=r.address, neighborhood=r.neighborhood
    )
    row = await _fetchrow(
        """
        INSERT INTO restaurants (
          name, neighborhood, cuisine, address, opened_date,
          opened_start_date, opened_end_date, opened_date_precision,
          is_upcoming, source_url, highlight_kind, identity_key
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (identity_key) DO UPDATE
        SET name = EXCLUDED.name,
            neighborhood = EXCLUDED.neighborhood,
            cuisine = EXCLUDED.cuisine,
            address = EXCLUDED.address,
            opened_date = EXCLUDED.opened_date,
            opened_start_date = EXCLUDED.opened_start_date,
            opened_end_date = EXCLUDED.opened_end_date,
            opened_date_precision = EXCLUDED.opened_date_precision,
            is_upcoming = EXCLUDED.is_upcoming,
            source_url = EXCLUDED.source_url,
            highlight_kind = EXCLUDED.highlight_kind
        RETURNING *
        """,
        r.name,
        r.neighborhood,
        r.cuisine,
        r.address,
        r.opened_date,
        _to_date(structured.start_date),
        _to_date(structured.end_date),
        structured.date_precision,
        structured.is_upcoming,
        r.source_url,
        r.highlight_kind,
        identity_key,
        pool=pool,
    )
    assert row is not None
    return _row_to_restaurant(row)


async def update_restaurant(
    id: int, r: NewRestaurant, *, pool: asyncpg.Pool | None = None
) -> StoredRestaurant:
    structured = derive_structured_date(r.opened_date)
    identity_key = build_restaurant_identity_key(
        name=r.name, address=r.address, neighborhood=r.neighborhood
    )
    row = await _fetchrow(
        """
        UPDATE restaurants
        SET name = $1,
            neighborhood = $2,
            cuisine = $3,
            address = $4,
            opened_date = $5,
            opened_start_date = $6,
            opened_end_date = $7,
            opened_date_precision = $8,
            is_upcoming = $9,
            source_url = $10,
            highlight_kind = $11,
            identity_key = $12
        WHERE id = $13
        RETURNING *
        """,
        r.name,
        r.neighborhood,
        r.cuisine,
        r.address,
        r.opened_date,
        _to_date(structured.start_date),
        _to_date(structured.end_date),
        structured.date_precision,
        structured.is_upcoming,
        r.source_url,
        r.highlight_kind,
        identity_key,
        id,
        pool=pool,
    )
    assert row is not None
    return _row_to_restaurant(row)


async def get_restaurant_by_identity_key(
    identity_key: str, *, pool: asyncpg.Pool | None = None
) -> StoredRestaurant | None:
    row = await _fetchrow(
        "SELECT * FROM restaurants WHERE identity_key = $1 LIMIT 1",
        identity_key,
        pool=pool,
    )
    return _row_to_restaurant(row) if row else None


async def get_restaurant_by_id(
    id: int, *, pool: asyncpg.Pool | None = None
) -> StoredRestaurant | None:
    row = await _fetchrow(
        "SELECT * FROM restaurants WHERE id = $1 LIMIT 1", id, pool=pool
    )
    return _row_to_restaurant(row) if row else None


async def get_restaurant_by_name(
    name: str, *, pool: asyncpg.Pool | None = None
) -> StoredRestaurant | None:
    row = await _fetchrow(
        "SELECT * FROM restaurants WHERE lower(name) = lower($1) LIMIT 1", name, pool=pool
    )
    return _row_to_restaurant(row) if row else None


async def clear_restaurants(*, pool: asyncpg.Pool | None = None) -> None:
    await _execute("DELETE FROM restaurants", pool=pool)


async def delete_restaurant(id: int, *, pool: asyncpg.Pool | None = None) -> None:
    await _execute("DELETE FROM restaurants WHERE id=$1", id, pool=pool)


# ── Push subscriptions ─────────────────────────────────────────────────────────


async def get_subscriptions(
    *, pool: asyncpg.Pool | None = None
) -> list[StoredPushSubscription]:
    rows = await _fetch(
        "SELECT * FROM push_subscriptions ORDER BY created_at ASC", pool=pool
    )
    return [_row_to_subscription(r) for r in rows]


async def add_subscription(
    endpoint: str,
    keys: PushKeys,
    preferences: PushPreferences | None = None,
    *,
    pool: asyncpg.Pool | None = None,
) -> StoredPushSubscription:
    normalized = normalize_push_preferences(preferences)
    row = await _fetchrow(
        """
        INSERT INTO push_subscriptions (endpoint, keys, preferences)
        VALUES ($1,$2,$3)
        ON CONFLICT (endpoint) DO UPDATE
        SET keys = EXCLUDED.keys,
            preferences = EXCLUDED.preferences,
            updated_at = NOW()
        RETURNING *
        """,
        endpoint,
        json.dumps(dict(keys)),
        json.dumps(normalized.model_dump()),
        pool=pool,
    )
    assert row is not None
    return _row_to_subscription(row)


async def get_subscription_by_endpoint(
    endpoint: str, *, pool: asyncpg.Pool | None = None
) -> StoredPushSubscription | None:
    row = await _fetchrow(
        "SELECT * FROM push_subscriptions WHERE endpoint = $1 LIMIT 1",
        endpoint,
        pool=pool,
    )
    return _row_to_subscription(row) if row else None


async def update_subscription_preferences(
    endpoint: str,
    preferences: PushPreferences,
    *,
    pool: asyncpg.Pool | None = None,
) -> StoredPushSubscription | None:
    row = await _fetchrow(
        """
        UPDATE push_subscriptions
        SET preferences = $2,
            updated_at = NOW()
        WHERE endpoint = $1
        RETURNING *
        """,
        endpoint,
        json.dumps(normalize_push_preferences(preferences).model_dump()),
        pool=pool,
    )
    return _row_to_subscription(row) if row else None


async def remove_subscription(
    endpoint: str, *, pool: asyncpg.Pool | None = None
) -> None:
    await _execute(
        "DELETE FROM push_subscriptions WHERE endpoint=$1", endpoint, pool=pool
    )


# ── Data updates ───────────────────────────────────────────────────────────────


async def get_recent_updates(
    limit: int = 50, *, pool: asyncpg.Pool | None = None
) -> list[DataUpdate]:
    rows = await _fetch(
        "SELECT * FROM data_updates ORDER BY occurred_at DESC LIMIT $1", limit, pool=pool
    )
    return [DataUpdate.model_validate(dict(r)) for r in rows]


async def get_latest_update_timestamp(
    *, pool: asyncpg.Pool | None = None
) -> datetime | None:
    row = await _fetchrow(
        "SELECT occurred_at FROM data_updates ORDER BY occurred_at DESC LIMIT 1",
        pool=pool,
    )
    return row["occurred_at"] if row else None


UpdateType = Literal["restaurant"]
UpdateAction = Literal["added", "removed", "updated"]


async def record_update(
    type_: UpdateType,
    item_name: str,
    action: UpdateAction,
    *,
    pool: asyncpg.Pool | None = None,
) -> DataUpdate:
    row = await _fetchrow(
        """
        INSERT INTO data_updates (type, item_name, action)
        VALUES ($1,$2,$3) RETURNING *
        """,
        type_,
        item_name,
        action,
        pool=pool,
    )
    assert row is not None
    return DataUpdate.model_validate(dict(row))


async def get_cron_run(
    job_name: str, *, pool: asyncpg.Pool | None = None
) -> CronRun | None:
    row = await _fetchrow(
        "SELECT * FROM cron_runs WHERE job_name = $1", job_name, pool=pool
    )
    return CronRun.model_validate(dict(row)) if row else None


async def mark_cron_run(job_name: str, *, pool: asyncpg.Pool | None = None) -> CronRun:
    row = await _fetchrow(
        """
        INSERT INTO cron_runs (job_name, last_ran_at)
        VALUES ($1, NOW())
        ON CONFLICT (job_name)
        DO UPDATE SET last_ran_at = EXCLUDED.last_ran_at
        RETURNING *
        """,
        job_name,
        pool=pool,
    )
    assert row is not None
    return CronRun.model_validate(dict(row))


# Suppress unused import warning for UTC/timedelta; reserved for future helpers.
_ = (UTC, timedelta)
