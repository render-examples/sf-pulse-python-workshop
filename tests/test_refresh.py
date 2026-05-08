"""Refresh pipeline integration tests — apply_discovered_items end-to-end."""

from __future__ import annotations

from unittest.mock import AsyncMock

import asyncpg

from app import refresh, storage


async def test_apply_discovered_items_adds_new_records(
    clean_db: asyncpg.Pool, monkeypatch
) -> None:
    broadcast_mock = AsyncMock()
    monkeypatch.setattr("app.refresh.broadcast", broadcast_mock)

    result = await refresh.apply_discovered_items(
        restaurants=[
            storage.NewRestaurant(
                name="Joe's", neighborhood="Mission", cuisine="Pizza", opened_date="April 15, 2026"
            )
        ],
        pool=clean_db,
    )

    assert result.added_restaurants == ["Joe's"]
    assert result.updated_restaurants == []
    assert broadcast_mock.await_count == 1
    channels = {call.args[0] for call in broadcast_mock.await_args_list}
    assert channels == {"restaurants"}


async def test_apply_discovered_items_blocks_named_filter(
    clean_db: asyncpg.Pool, monkeypatch
) -> None:
    monkeypatch.setattr("app.refresh.broadcast", AsyncMock())

    result = await refresh.apply_discovered_items(
        restaurants=[
            storage.NewRestaurant(
                name="Insider Tip",  # blocked phrase
                neighborhood="Mission",
                cuisine="Pizza",
                opened_date="April 15, 2026",
            )
        ],
        pool=clean_db,
    )
    assert result.added_restaurants == []
    rows = await clean_db.fetch("SELECT COUNT(*) AS c FROM restaurants")
    assert rows[0]["c"] == 0


async def test_apply_discovered_items_updates_on_changed_field(
    clean_db: asyncpg.Pool, monkeypatch
) -> None:
    monkeypatch.setattr("app.refresh.broadcast", AsyncMock())

    initial = storage.NewRestaurant(
        name="Joe's",
        neighborhood="Mission",
        cuisine="Pizza",
        opened_date="April 2026",
        address="123 Mission St",
    )
    await refresh.apply_discovered_items(restaurants=[initial], pool=clean_db)

    # Same identity (name+address), more precise opened_date → triggers update.
    refined = storage.NewRestaurant(
        name="Joe's",
        neighborhood="Mission",
        cuisine="Pizza",
        opened_date="April 15, 2026",
        address="123 Mission St",
    )
    result = await refresh.apply_discovered_items(restaurants=[refined], pool=clean_db)
    assert result.added_restaurants == []
    assert result.updated_restaurants == ["Joe's"]


async def test_run_daily_refresh_works_without_workflows_runtime(monkeypatch) -> None:
    """Local-seed entrypoint must run without the Render Workflows SDK runtime.

    Regression guard: calling daily_refresh() (the @app.task) outside the runtime
    fails with a ContextVar LookupError. run_daily_refresh() is the plain path
    documented for local seeding and must keep working. With all sources empty
    the DB is never touched, so this test runs without Docker.
    """

    async def _empty() -> list:
        return []

    for path in (
        "app.sources.eater.fetch_eater_sf_articles",
        "app.sources.sfist.fetch_sfist_restaurants",
        "app.sources.michelin.fetch_michelin_restaurants",
        "app.sources.ddg_search.search_restaurants_ddg",
    ):
        monkeypatch.setattr(path, _empty)

    result = await refresh.run_daily_refresh()
    assert result == {"restaurants": 0}


async def test_push_skipped_when_vapid_not_configured(
    clean_db: asyncpg.Pool, monkeypatch, caplog
) -> None:
    """With no VAPID keys (default in test env), push fan-out short-circuits."""
    monkeypatch.setattr("app.refresh.broadcast", AsyncMock())

    # Pre-seed a subscription so that if push WERE enabled, it would try to send.
    await storage.add_subscription(
        endpoint="https://fcm.googleapis.com/fcm/send/abc",
        keys={"p256dh": "x" * 10, "auth": "y" * 10},
        pool=clean_db,
    )

    # Use a sentinel by spying on send_push — it must NOT be invoked.
    send_mock = AsyncMock()
    monkeypatch.setattr("app.refresh.send_push", send_mock)

    await refresh.apply_discovered_items(
        restaurants=[
            storage.NewRestaurant(
                name="Joe's",
                neighborhood="Mission",
                cuisine="Pizza",
                opened_date="April 15, 2026",
            )
        ],
        pool=clean_db,
    )
    assert send_mock.await_count == 0
