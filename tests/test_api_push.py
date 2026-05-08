"""Push notification API tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_vapid_key_returns_503_when_not_configured(client: AsyncClient) -> None:
    resp = await client.get("/api/push/vapid-key")
    # Test env has empty VAPID keys → 503.
    assert resp.status_code == 503


async def test_subscribe_with_trusted_endpoint(
    client: AsyncClient, clean_db
) -> None:
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abcd",
        "keys": {"p256dh": "BPfAKey", "auth": "AuthKey"},
    }
    resp = await client.post("/api/push/subscribe", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoint"] == payload["endpoint"]


async def test_subscribe_rejects_untrusted_endpoint(client: AsyncClient) -> None:
    payload = {
        "endpoint": "https://evil.example.com/push/abc",
        "keys": {"p256dh": "x", "auth": "y"},
    }
    resp = await client.post("/api/push/subscribe", json=payload)
    assert resp.status_code == 422  # Pydantic validation failure


async def test_subscription_lookup(client: AsyncClient, clean_db) -> None:
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/lookup",
        "keys": {"p256dh": "k1", "auth": "k2"},
    }
    await client.post("/api/push/subscribe", json=payload)

    found = await client.get(
        "/api/push/subscription", params={"endpoint": payload["endpoint"]}
    )
    assert found.status_code == 200
    assert found.json()["endpoint"] == payload["endpoint"]

    missing = await client.get(
        "/api/push/subscription",
        params={"endpoint": "https://fcm.googleapis.com/fcm/send/missing"},
    )
    assert missing.status_code == 404


async def test_preferences_update(client: AsyncClient, clean_db) -> None:
    endpoint = "https://fcm.googleapis.com/fcm/send/prefs"
    sub_payload = {
        "endpoint": endpoint,
        "keys": {"p256dh": "p", "auth": "a"},
    }
    await client.post("/api/push/subscribe", json=sub_payload)

    update_payload = {
        "endpoint": endpoint,
        "preferences": {
            "neighborhoods": ["Mission"],
            "cuisines": ["Pizza"],
        },
    }
    resp = await client.post("/api/push/preferences", json=update_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferences"]["neighborhoods"] == ["Mission"]
