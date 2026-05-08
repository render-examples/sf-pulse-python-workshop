"""Storage layer tests — exercise CRUD + ON CONFLICT semantics."""

from __future__ import annotations

import asyncpg

from app import storage


async def test_add_and_get_restaurant(clean_db: asyncpg.Pool) -> None:
    r = await storage.add_restaurant(
        storage.NewRestaurant(
            name="Joe's",
            neighborhood="Mission",
            cuisine="Pizza",
            opened_date="April 15, 2026",
            address="123 Mission St",
        ),
        pool=clean_db,
    )
    assert r.id > 0
    assert r.name == "Joe's"
    assert r.opened_start_date == "2026-04-15"
    assert r.opened_date_precision == "day"

    fetched = await storage.get_restaurant_by_id(r.id, pool=clean_db)
    assert fetched is not None
    assert fetched.id == r.id


async def test_add_restaurant_on_conflict_updates(clean_db: asyncpg.Pool) -> None:
    first = await storage.add_restaurant(
        storage.NewRestaurant(
            name="Joe's",
            neighborhood="Mission",
            cuisine="Pizza",
            opened_date="April 15, 2026",
            address="123 Mission St",
        ),
        pool=clean_db,
    )
    # Same identity (name + address), changed cuisine → ON CONFLICT updates.
    second = await storage.add_restaurant(
        storage.NewRestaurant(
            name="Joe's",
            neighborhood="Mission",
            cuisine="Neapolitan Pizza",
            opened_date="April 15, 2026",
            address="123 Mission St",
        ),
        pool=clean_db,
    )
    assert second.id == first.id
    assert second.cuisine == "Neapolitan Pizza"

    rows = await clean_db.fetch("SELECT COUNT(*) AS c FROM restaurants")
    assert rows[0]["c"] == 1


async def test_delete_restaurant_removes_row(clean_db: asyncpg.Pool) -> None:
    r = await storage.add_restaurant(
        storage.NewRestaurant(
            name="Joe's", neighborhood="Mission", cuisine="Pizza", opened_date="May 1, 2026"
        ),
        pool=clean_db,
    )
    await storage.delete_restaurant(r.id, pool=clean_db)
    assert await storage.get_restaurant_by_id(r.id, pool=clean_db) is None


async def test_subscription_crud(clean_db: asyncpg.Pool) -> None:
    sub = await storage.add_subscription(
        endpoint="https://fcm.googleapis.com/fcm/send/abc",
        keys={"p256dh": "x" * 10, "auth": "y" * 10},
        pool=clean_db,
    )
    assert sub.endpoint == "https://fcm.googleapis.com/fcm/send/abc"

    fetched = await storage.get_subscription_by_endpoint(sub.endpoint, pool=clean_db)
    assert fetched is not None
    assert fetched.id == sub.id

    from app.shared.types import PushPreferences

    updated = await storage.update_subscription_preferences(
        sub.endpoint, PushPreferences(neighborhoods=["Mission"]), pool=clean_db
    )
    assert updated is not None
    assert updated.preferences.neighborhoods == ["Mission"]

    await storage.remove_subscription(sub.endpoint, pool=clean_db)
    assert await storage.get_subscription_by_endpoint(sub.endpoint, pool=clean_db) is None


async def test_subscription_on_conflict_updates_keys(clean_db: asyncpg.Pool) -> None:
    endpoint = "https://fcm.googleapis.com/fcm/send/dup"
    first = await storage.add_subscription(
        endpoint=endpoint,
        keys={"p256dh": "a" * 5, "auth": "b" * 5},
        pool=clean_db,
    )
    second = await storage.add_subscription(
        endpoint=endpoint,
        keys={"p256dh": "c" * 5, "auth": "d" * 5},
        pool=clean_db,
    )
    assert second.id == first.id
    assert second.keys["p256dh"] == "c" * 5


async def test_data_updates_recorded(clean_db: asyncpg.Pool) -> None:
    update = await storage.record_update("restaurant", "Joe's", "added", pool=clean_db)
    assert update.id > 0

    recent = await storage.get_recent_updates(10, pool=clean_db)
    assert len(recent) == 1
    assert recent[0].item_name == "Joe's"

    ts = await storage.get_latest_update_timestamp(pool=clean_db)
    assert ts is not None


async def test_cron_runs_upserts_timestamp(clean_db: asyncpg.Pool) -> None:
    first = await storage.mark_cron_run("daily", pool=clean_db)
    second = await storage.mark_cron_run("daily", pool=clean_db)
    assert first.job_name == "daily"
    assert second.last_ran_at >= first.last_ran_at

    fetched = await storage.get_cron_run("daily", pool=clean_db)
    assert fetched is not None
