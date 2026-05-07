from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypeVar

from app.config import get_settings
from app.llm import get_llm_client
from app.llm.pipeline import (
    extract_events_from_articles,
    extract_restaurants_from_articles,
)
from app.shared.identity import build_event_identity_key
from app.sources.types import RawArticle
from app.storage import NewEvent, NewRestaurant
from workflow._app import app
from workflow.tasks.apply_discovered_items import apply_discovered_items
from workflow.tasks.fetch_cal_academy import fetch_cal_academy
from workflow.tasks.fetch_eater_sf import fetch_eater_sf
from workflow.tasks.fetch_famsf import fetch_famsf
from workflow.tasks.fetch_funcheap import fetch_funcheap
from workflow.tasks.fetch_michelin import fetch_michelin
from workflow.tasks.fetch_sfist import fetch_sfist
from workflow.tasks.search_events import search_events
from workflow.tasks.search_restaurants import search_restaurants

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _settled(result: Any, label: str, fallback: T) -> T:
    if isinstance(result, BaseException):
        logger.warning("[workflow] source failed (%s): %r", label, result)
        return fallback
    return result


def _to_raw_articles(items: list[dict[str, Any]]) -> list[RawArticle]:
    return [RawArticle.model_validate(item) for item in items]


def _to_new_restaurants(items: list[dict[str, Any]]) -> list[NewRestaurant]:
    return [NewRestaurant(**item) for item in items]


def _to_new_events(items: list[dict[str, Any]]) -> list[NewEvent]:
    return [NewEvent(**item) for item in items]


def _dedup_restaurants(items: list[NewRestaurant]) -> list[NewRestaurant]:
    seen: set[str] = set()
    result: list[NewRestaurant] = []
    for r in items:
        key = r.name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


def _dedup_events(items: list[NewEvent]) -> list[NewEvent]:
    seen: set[str] = set()
    result: list[NewEvent] = []
    for e in items:
        key = build_event_identity_key(
            title=e.title,
            location=e.location,
            date_text=e.date,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result


@app.task(name="daily-refresh", timeout_seconds=600)
async def daily_refresh() -> dict[str, int]:
    logger.info("[workflow] SF Pulse refresh — %s", datetime.now(UTC).isoformat())

    settings = get_settings()
    llm = get_llm_client() if settings.llm_api_key else None
    if llm:
        logger.info("[workflow] LLM client configured, using LLM extraction")
    else:
        logger.info(
            "[workflow] no LLM_API_KEY set, using regex-only sources (SFist, Michelin)"
        )

    logger.info("[workflow] fetching restaurant sources...")
    eater_raw, sfist_raw, michelin_raw, ddg_r_raw = await asyncio.gather(
        fetch_eater_sf(),
        fetch_sfist(),
        fetch_michelin(),
        search_restaurants(),
        return_exceptions=True,
    )

    eater_articles = _to_raw_articles(_settled(eater_raw, "Eater SF", []))
    sfist_items = _to_new_restaurants(_settled(sfist_raw, "SFist", []))
    michelin_items = _to_new_restaurants(_settled(michelin_raw, "Michelin", []))
    ddg_restaurant_articles = _to_raw_articles(
        _settled(ddg_r_raw, "DDG restaurants", [])
    )

    logger.info("[workflow] fetching event sources...")
    funcheap_raw, famsf_raw, cal_academy_raw, ddg_e_raw = await asyncio.gather(
        fetch_funcheap(),
        fetch_famsf(),
        fetch_cal_academy(),
        search_events(),
        return_exceptions=True,
    )

    funcheap_events = _to_new_events(_settled(funcheap_raw, "Funcheap", []))
    famsf_events = _to_new_events(_settled(famsf_raw, "FAMSF", []))
    cal_academy_events = _to_new_events(_settled(cal_academy_raw, "Cal Academy", []))
    ddg_event_articles = _to_raw_articles(_settled(ddg_e_raw, "DDG events", []))

    llm_restaurants: list[NewRestaurant] = []
    llm_events: list[NewEvent] = []

    if llm is not None:
        logger.info("[workflow] running LLM extraction...")
        r_results, e_results = await asyncio.gather(
            asyncio.gather(
                extract_restaurants_from_articles(llm, eater_articles),
                extract_restaurants_from_articles(llm, ddg_restaurant_articles),
                return_exceptions=True,
            ),
            asyncio.gather(
                extract_events_from_articles(llm, ddg_event_articles),
                return_exceptions=True,
            ),
            return_exceptions=True,
        )

        if not isinstance(r_results, BaseException):
            for r in r_results:
                llm_restaurants.extend(_settled(r, "LLM restaurants", []))

        if not isinstance(e_results, BaseException):
            for e in e_results:
                llm_events.extend(_settled(e, "LLM events", []))

        logger.info(
            "[workflow] LLM extracted: %d restaurants, %d events",
            len(llm_restaurants),
            len(llm_events),
        )

    restaurants = _dedup_restaurants(
        [*sfist_items, *michelin_items, *llm_restaurants]
    )
    events = _dedup_events(
        [*funcheap_events, *famsf_events, *cal_academy_events, *llm_events]
    )

    logger.info(
        "[workflow] candidates: %d restaurants, %d events",
        len(restaurants),
        len(events),
    )

    if restaurants or events:
        await apply_discovered_items(
            restaurants=[asdict(r) for r in restaurants],
            events=[asdict(e) for e in events],
        )
    else:
        logger.info("[workflow] nothing new")

    return {"restaurants": len(restaurants), "events": len(events)}
