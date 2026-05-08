"""Tests for app.shared.filters."""

from __future__ import annotations

from app.shared.filters import (
    RestaurantFilters,
    apply_restaurant_filters,
    parse_home_filters,
)
from app.shared.types import Restaurant


def _restaurant(**overrides) -> Restaurant:
    base = {
        "id": 1,
        "name": "Joe's Pizza",
        "neighborhood": "Mission",
        "cuisine": "Pizza",
        "address": None,
        "opened_date": "April 15, 2026",
        "opened_start_date": "2026-04-15",
        "opened_end_date": "2026-04-15",
        "opened_date_precision": "day",
        "is_upcoming": False,
        "highlight_kind": "opening",
        "source_url": None,
    }
    base.update(overrides)
    return Restaurant.model_validate(base)


def test_parse_home_filters_extracts_query_params() -> None:
    filters = parse_home_filters(
        {
            "r-q": "pizza",
            "r-neighborhood": "Mission,SoMa",
            "r-upcoming": "1",
            "r-from": "2026-05-01",
            "r-to": "2026-08-31",
        }
    )
    assert filters.restaurants.query == "pizza"
    assert filters.restaurants.neighborhoods == ["Mission", "SoMa"]
    assert filters.restaurants.upcoming_only is True
    assert filters.restaurants.from_date == "2026-05-01"
    assert filters.restaurants.to_date == "2026-08-31"


def test_parse_home_filters_drops_invalid_iso_date() -> None:
    filters = parse_home_filters({"r-from": "not-a-date"})
    assert filters.restaurants.from_date == ""


def test_apply_restaurant_filters_query_searches_all_fields() -> None:
    items = [
        _restaurant(id=1, name="Joe's Pizza"),
        _restaurant(id=2, name="Sushi Place", cuisine="Sushi"),
    ]
    out = apply_restaurant_filters(items, RestaurantFilters(query="pizza"))
    assert [r.id for r in out] == [1]


def test_apply_restaurant_filters_neighborhood() -> None:
    items = [
        _restaurant(id=1, neighborhood="Mission"),
        _restaurant(id=2, neighborhood="SoMa"),
    ]
    out = apply_restaurant_filters(items, RestaurantFilters(neighborhoods=["SoMa"]))
    assert [r.id for r in out] == [2]


def test_apply_restaurant_filters_combined() -> None:
    items = [
        _restaurant(id=1, neighborhood="Mission", cuisine="Pizza"),
        _restaurant(id=2, neighborhood="Mission", cuisine="Thai"),
        _restaurant(id=3, neighborhood="SoMa", cuisine="Pizza"),
    ]
    out = apply_restaurant_filters(
        items, RestaurantFilters(neighborhoods=["Mission"], cuisines=["Pizza"])
    )
    assert [r.id for r in out] == [1]
