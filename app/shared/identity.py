"""Identity-key builder — port of shared/restaurant-identity.ts."""

from __future__ import annotations


def _normalize_part(value: str | None) -> str:
    return (value or "").strip().lower()


def build_restaurant_identity_key(
    *, name: str, address: str | None = None, neighborhood: str | None = None
) -> str:
    secondary = _normalize_part(address) or _normalize_part(neighborhood)
    return f"{_normalize_part(name)}|{secondary}"


def build_event_identity_key(*, title: str, location: str, date_text: str) -> str:
    return "|".join(
        [_normalize_part(title), _normalize_part(location), _normalize_part(date_text)]
    )
