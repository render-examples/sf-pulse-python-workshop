"""Security helpers — port of server/security.ts.

VAPID config, trusted-host validation, secrets comparison, and Pydantic
schemas for push subscription / preferences endpoints.
"""

from __future__ import annotations

import hmac
import json
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.shared.catalog import normalize_push_preferences
from app.shared.types import PushPreferences

TRUSTED_PUSH_HOSTS: set[str] = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
    "notify.windows.com",
}

TRUSTED_PUSH_HOST_SUFFIXES: tuple[str, ...] = (
    ".push.apple.com",
    ".notify.windows.com",
)

def is_trusted_push_endpoint(endpoint: str) -> bool:
    try:
        parsed = urlparse(endpoint)
    except (ValueError, AttributeError):
        return False
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return host in TRUSTED_PUSH_HOSTS or any(
        host.endswith(suffix) for suffix in TRUSTED_PUSH_HOST_SUFFIXES
    )


def secrets_equal(expected: str, actual: object) -> bool:
    if not isinstance(actual, str):
        return False
    if len(expected) != len(actual):
        return False
    return hmac.compare_digest(expected.encode(), actual.encode())


def get_public_app_url() -> str:
    settings = get_settings()
    return settings.public_app_url


def serialize_for_inline_script(value: object) -> str:
    """JSON for inline <script> blocks; escape characters that would break out of <script>."""
    return (
        json.dumps(value, default=str)
        .replace("<", "\\u003C")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class PushKeysPayload(BaseModel):
    model_config = {"extra": "forbid"}
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)


class PushPreferencesPayload(BaseModel):
    model_config = {"extra": "forbid"}
    neighborhoods: list[str] = Field(default_factory=list)
    cuisines: list[str] = Field(default_factory=list)

    @field_validator("neighborhoods", "cuisines")
    @classmethod
    def _strings_within_limits(cls, value: list[str], info) -> list[str]:
        max_len = 120 if info.field_name == "neighborhoods" else 160
        for v in value:
            if not v or len(v) > max_len:
                raise ValueError(f"{info.field_name} entries must be 1..{max_len} chars")
        return value

    def normalized(self) -> PushPreferences:
        return normalize_push_preferences(self.model_dump())


def _validate_endpoint(value: str) -> str:
    if not (1 <= len(value) <= 2048):
        raise ValueError("endpoint must be 1..2048 chars")
    if not is_trusted_push_endpoint(value):
        raise ValueError("Push endpoint must use a trusted web-push provider")
    return value


class PushSubscriptionPayload(BaseModel):
    model_config = {"extra": "forbid"}
    endpoint: str
    keys: PushKeysPayload
    preferences: PushPreferencesPayload | None = None

    @field_validator("endpoint")
    @classmethod
    def _check_endpoint(cls, value: str) -> str:
        return _validate_endpoint(value)


class UnsubscribePayload(BaseModel):
    model_config = {"extra": "forbid"}
    endpoint: str

    @field_validator("endpoint")
    @classmethod
    def _check_endpoint(cls, value: str) -> str:
        return _validate_endpoint(value)


class SubscriptionLookup(BaseModel):
    model_config = {"extra": "forbid"}
    endpoint: str

    @field_validator("endpoint")
    @classmethod
    def _check_endpoint(cls, value: str) -> str:
        return _validate_endpoint(value)


class PushPreferencesUpdatePayload(BaseModel):
    model_config = {"extra": "forbid"}
    endpoint: str
    preferences: PushPreferencesPayload

    @field_validator("endpoint")
    @classmethod
    def _check_endpoint(cls, value: str) -> str:
        return _validate_endpoint(value)


# Re-export for callers
__all__ = [
    "PushKeysPayload",
    "PushPreferencesPayload",
    "PushPreferencesUpdatePayload",
    "PushSubscriptionPayload",
    "SubscriptionLookup",
    "UnsubscribePayload",
    "get_public_app_url",
    "is_trusted_push_endpoint",
    "secrets_equal",
    "serialize_for_inline_script",
]
