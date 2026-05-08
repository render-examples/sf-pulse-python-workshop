"""Event API endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient

from app import storage


async def test_list_events_returns_seeded(client: AsyncClient, clean_db) -> None:
    await storage.clear_events(pool=clean_db)
    await storage.add_event(
        storage.NewEvent(
            title="Mission Block Party",
            location="24th Street, Mission",
            date="April 15, 2026",
            time="2:00 PM - 8:00 PM",
            description="Live music, food trucks, and local art.",
            source_url="https://example.com/event",
        ),
        pool=clean_db,
    )
    resp = await client.get("/api/events")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Mission Block Party"
    assert body[0]["location"] == "24th Street, Mission"


async def test_get_event_by_id(client: AsyncClient, clean_db) -> None:
    await storage.clear_events(pool=clean_db)
    e = await storage.add_event(
        storage.NewEvent(
            title="Carnaval Parade",
            location="Mission District",
            date="May 24, 2026",
        ),
        pool=clean_db,
    )
    resp = await client.get(f"/api/events/{e.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == e.id
    assert resp.json()["title"] == "Carnaval Parade"

    miss = await client.get("/api/events/99999")
    assert miss.status_code == 404


async def test_delete_event_requires_cron_secret(
    client: AsyncClient, clean_db, cron_headers
) -> None:
    await storage.clear_events(pool=clean_db)
    e = await storage.add_event(
        storage.NewEvent(
            title="Roxie Screening",
            location="Roxie Theater, 3117 16th St, Mission",
            date="April 5, 2026",
        ),
        pool=clean_db,
    )
    no_secret = await client.delete(f"/api/events/{e.id}")
    assert no_secret.status_code == 401

    with_secret = await client.delete(f"/api/events/{e.id}", headers=cron_headers)
    assert with_secret.status_code == 200
    assert with_secret.json() == {"ok": True}
    assert await storage.get_event_by_id(e.id, pool=clean_db) is None
