"""Security helpers — endpoint trust + secrets comparison."""

from __future__ import annotations

import pytest

from app.security import (
    PushPreferencesPayload,
    is_trusted_push_endpoint,
    secrets_equal,
)


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("https://fcm.googleapis.com/fcm/send/abc", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://push.services.mozilla.com/wpush/v2/abc", True),
        ("https://api.push.apple.com/3/device/abc", True),  # subdomain match
        ("https://web.push.apple.com/abc", True),
        ("https://abc.notify.windows.com/foo", True),
        ("https://notify.windows.com/foo", True),
        ("https://evil.example.com/push", False),
        ("http://fcm.googleapis.com/fcm/send/abc", False),  # plain http rejected
        ("https://user:pass@fcm.googleapis.com/fcm/send/abc", False),  # creds rejected
        ("not-a-url", False),
    ],
)
def test_is_trusted_push_endpoint_matrix(endpoint: str, expected: bool) -> None:
    assert is_trusted_push_endpoint(endpoint) is expected


def test_secrets_equal_constant_time() -> None:
    assert secrets_equal("abc", "abc") is True
    assert secrets_equal("abc", "abd") is False
    assert secrets_equal("abc", "abcd") is False  # different length
    assert secrets_equal("abc", None) is False
    assert secrets_equal("abc", 123) is False  # non-string


def test_push_preferences_payload_rejects_long_neighborhood() -> None:
    too_long = "x" * 200
    with pytest.raises(Exception):
        PushPreferencesPayload(neighborhoods=[too_long])


def test_push_preferences_payload_normalized() -> None:
    payload = PushPreferencesPayload(
        neighborhoods=["Mission", "Mission"],
        cuisines=["Pizza"],
    )
    normalized = payload.normalized()
    assert normalized.neighborhoods == ["Mission"]
    assert normalized.cuisines == ["Pizza"]
