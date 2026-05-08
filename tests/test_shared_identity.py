"""Tests for app.shared.identity."""

from __future__ import annotations

from app.shared.identity import build_restaurant_identity_key


def test_restaurant_key_prefers_address_over_neighborhood() -> None:
    a = build_restaurant_identity_key(
        name="Joe's", address="123 Mission St", neighborhood="Mission"
    )
    assert a == "joe's|123 mission st"


def test_restaurant_key_falls_back_to_neighborhood() -> None:
    a = build_restaurant_identity_key(name="Joe's", address=None, neighborhood="Mission")
    assert a == "joe's|mission"


def test_restaurant_key_empty_secondary_when_both_missing() -> None:
    assert build_restaurant_identity_key(name="Joe's") == "joe's|"


def test_restaurant_key_case_insensitive() -> None:
    a = build_restaurant_identity_key(name="Joe's", address="123 Mission St")
    b = build_restaurant_identity_key(name="JOE'S", address="123 mission ST")
    assert a == b
