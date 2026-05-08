"""Tests for app.shared.catalog."""

from __future__ import annotations

from app.shared.catalog import (
    group_by_neighborhood,
    normalize_push_preferences,
    restaurant_matches_push_preferences,
)
from app.shared.types import PushPreferences, Restaurant


def _restaurant(**overrides) -> Restaurant:
    base = {
        "id": 1,
        "name": "Joe's",
        "neighborhood": "Mission",
        "cuisine": "Pizza",
        "address": None,
        "opened_date": "May 1, 2026",
        "opened_start_date": "2026-05-01",
        "opened_end_date": "2026-05-31",
        "opened_date_precision": "month",
        "is_upcoming": False,
        "highlight_kind": "opening",
        "source_url": None,
    }
    base.update(overrides)
    return Restaurant.model_validate(base)


def test_normalize_push_preferences_dedupes_and_sorts() -> None:
    out = normalize_push_preferences(
        {
            "neighborhoods": ["Mission", "mission ", "SoMa"],
            "cuisines": ["Pizza", "Pizza", "Thai"],
        }
    )
    assert out.neighborhoods == ["Mission", "SoMa", "mission"]
    assert out.cuisines == ["Pizza", "Thai"]


def test_normalize_push_preferences_none_returns_empty() -> None:
    out = normalize_push_preferences(None)
    assert out.neighborhoods == []
    assert out.cuisines == []


def test_restaurant_matches_when_no_prefs_set() -> None:
    assert restaurant_matches_push_preferences(_restaurant(), PushPreferences()) is True


def test_restaurant_matches_neighborhood_filter() -> None:
    prefs = PushPreferences(neighborhoods=["Mission"])
    assert restaurant_matches_push_preferences(_restaurant(neighborhood="Mission"), prefs) is True
    assert restaurant_matches_push_preferences(_restaurant(neighborhood="SoMa"), prefs) is False


def test_group_by_neighborhood_buckets_correctly() -> None:
    restaurants = [_restaurant(neighborhood="Mission"), _restaurant(id=2, neighborhood="Unknown")]
    grouped = group_by_neighborhood(restaurants)
    assert len(grouped["Mission"].restaurants) == 1
    assert len(grouped["Other SF"].restaurants) == 1  # "Unknown" → fallback
