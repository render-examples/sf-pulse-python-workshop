"""Neighborhoods + push preference matching — port of shared/catalog.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.shared.types import PushPreferences, Restaurant


@dataclass(frozen=True)
class NeighborhoodCenter:
    lat: float
    lng: float


@dataclass(frozen=True)
class NeighborhoodAlias:
    label: str
    center: NeighborhoodCenter
    patterns: tuple[re.Pattern[str], ...]


def _re(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


NEIGHBORHOOD_ALIASES: tuple[NeighborhoodAlias, ...] = (
    NeighborhoodAlias("Mission", NeighborhoodCenter(37.7599, -122.4148), (_re(r"\bmission\b"), _re(r"dolores park"), _re(r"mission st"))),
    NeighborhoodAlias("SoMa", NeighborhoodCenter(37.7785, -122.3950), (_re(r"\bsoma\b"), _re(r"south of market"))),
    NeighborhoodAlias("Potrero Hill", NeighborhoodCenter(37.7605, -122.3926), (_re(r"potrero hill"), _re(r"vermont & 20th"))),
    NeighborhoodAlias("Golden Gate Park", NeighborhoodCenter(37.7694, -122.4862), (_re(r"golden gate park"), _re(r"hippie hill"))),
    NeighborhoodAlias("Financial District", NeighborhoodCenter(37.7946, -122.3999), (_re(r"financial district"), _re(r"main to great highway"))),
    NeighborhoodAlias("Civic Center", NeighborhoodCenter(37.7793, -122.4158), (_re(r"civic center"), _re(r"main public library"))),
    NeighborhoodAlias("Marina", NeighborhoodCenter(37.8015, -122.4368), (_re(r"marina"), _re(r"fort mason"))),
    NeighborhoodAlias("Yerba Buena", NeighborhoodCenter(37.7854, -122.4005), (_re(r"yerba buena"),)),
    NeighborhoodAlias("Haight", NeighborhoodCenter(37.7692, -122.4481), (_re(r"\bhaight\b"),)),
    NeighborhoodAlias("Sunset", NeighborhoodCenter(37.7533, -122.4946), (_re(r"sunset"),)),
    NeighborhoodAlias("Richmond", NeighborhoodCenter(37.7800, -122.4784), (_re(r"richmond"),)),
    NeighborhoodAlias("Castro", NeighborhoodCenter(37.7609, -122.4350), (_re(r"castro"),)),
)

OTHER_SF_NEIGHBORHOOD = NeighborhoodAlias(
    "Other SF", NeighborhoodCenter(37.7749, -122.4194), ()
)

ALL_NEIGHBORHOODS: tuple[NeighborhoodAlias, ...] = (*NEIGHBORHOOD_ALIASES, OTHER_SF_NEIGHBORHOOD)


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({v for v in values if v})


def normalize_push_preferences(prefs: PushPreferences | dict | None) -> PushPreferences:
    if prefs is None:
        prefs_dict: dict = {}
    elif isinstance(prefs, PushPreferences):
        prefs_dict = prefs.model_dump()
    else:
        prefs_dict = prefs

    neighborhoods = _unique_sorted([str(v).strip() for v in (prefs_dict.get("neighborhoods") or [])])
    cuisines = _unique_sorted([str(v).strip() for v in (prefs_dict.get("cuisines") or [])])
    return PushPreferences(neighborhoods=neighborhoods, cuisines=cuisines)


def has_push_preferences(prefs: PushPreferences) -> bool:
    return bool(prefs.neighborhoods or prefs.cuisines)


def get_restaurant_neighborhood_options(restaurants: list[Restaurant]) -> list[str]:
    return _unique_sorted([r.neighborhood for r in restaurants])


def get_restaurant_cuisine_options(restaurants: list[Restaurant]) -> list[str]:
    return _unique_sorted([r.cuisine for r in restaurants])


def matches_preferred_neighborhood(neighborhood: str, prefs: PushPreferences) -> bool:
    if not prefs.neighborhoods:
        return True
    norm = _normalize_text(neighborhood)
    return any(_normalize_text(v) == norm for v in prefs.neighborhoods)


def matches_preferred_cuisine(cuisine: str, prefs: PushPreferences) -> bool:
    if not prefs.cuisines:
        return True
    norm = _normalize_text(cuisine)
    return any(_normalize_text(v) == norm for v in prefs.cuisines)


def restaurant_matches_push_preferences(restaurant: Restaurant, prefs: PushPreferences) -> bool:
    return matches_preferred_neighborhood(
        restaurant.neighborhood, prefs
    ) and matches_preferred_cuisine(restaurant.cuisine, prefs)


def find_nearest_neighborhood(lat: float, lng: float) -> NeighborhoodAlias:
    best = ALL_NEIGHBORHOODS[0]
    best_dist = float("inf")
    for entry in ALL_NEIGHBORHOODS:
        d_lat = lat - entry.center.lat
        d_lng = lng - entry.center.lng
        dist = d_lat * d_lat + d_lng * d_lng
        if dist < best_dist:
            best_dist = dist
            best = entry
    return best


@dataclass
class NeighborhoodGroup:
    restaurants: list[Restaurant]


def group_by_neighborhood(restaurants: list[Restaurant]) -> dict[str, NeighborhoodGroup]:
    groups: dict[str, NeighborhoodGroup] = {a.label: NeighborhoodGroup([]) for a in ALL_NEIGHBORHOODS}
    for r in restaurants:
        key = r.neighborhood if r.neighborhood in groups else "Other SF"
        groups[key].restaurants.append(r)
    return groups
