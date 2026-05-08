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
from app.refresh import dedup_events, dedup_restaurants
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


def _coerce_list(items: Any) -> list[dict[str, Any]]:
    # The Render Workflows SDK auto-unwraps single-element list results when a
    # subtask returns a list of length 1 (see render_sdk/workflows/client.py
    # `run_subtask`). That means a fetcher returning [one_dict] comes back here
    # as one_dict, not [one_dict]. Normalize so the conversion shims see a list.
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return items
    return []


def _to_raw_articles(items: Any) -> list[RawArticle]:
    return [RawArticle.model_validate(item) for item in _coerce_list(items)]


def _to_new_restaurants(items: Any) -> list[NewRestaurant]:
    return [NewRestaurant(**item) for item in _coerce_list(items)]


def _to_new_events(items: Any) -> list[NewEvent]:
    return [NewEvent(**item) for item in _coerce_list(items)]


@app.task(name="daily-refresh", timeout_seconds=600)
async def daily_refresh() -> dict[str, int]:
    logger.info("[workflow] SF Pulse refresh — %s", datetime.now(UTC).isoformat())

    settings = get_settings()
    llm = get_llm_client() if settings.llm_api_key else None
    if llm:
        logger.info("[workflow] LLM client configured, using LLM extraction")
    else:
        logger.info(
            "[workflow] no LLM_API_KEY set, using regex-only sources (SFist, Michelin, Funcheap, FAMSF, Cal Academy)"
        )

    logger.info("[workflow] fetching restaurant + event sources...")
    (
        eater_raw,
        sfist_raw,
        michelin_raw,
        ddg_r_raw,
        funcheap_raw,
        famsf_raw,
        cal_academy_raw,
        ddg_e_raw,
    ) = await asyncio.gather(
        fetch_eater_sf(),
        fetch_sfist(),
        fetch_michelin(),
        search_restaurants(),
        fetch_funcheap(),
        fetch_famsf(),
        fetch_cal_academy(),
        search_events(),
        return_exceptions=True,
    )

    eater_articles = _to_raw_articles(_settled(eater_raw, "Eater SF", []))
    sfist_items = _to_new_restaurants(_settled(sfist_raw, "SFist", []))
    michelin_items = _to_new_restaurants(_settled(michelin_raw, "Michelin", []))
    ddg_restaurant_articles = _to_raw_articles(
        _settled(ddg_r_raw, "DDG restaurants", [])
    )

    funcheap_events = _to_new_events(_settled(funcheap_raw, "Funcheap", []))
    famsf_events = _to_new_events(_settled(famsf_raw, "FAMSF", []))
    cal_academy_events = _to_new_events(_settled(cal_academy_raw, "Cal Academy", []))
    ddg_event_articles = _to_raw_articles(_settled(ddg_e_raw, "DDG events", []))

    llm_restaurants: list[NewRestaurant] = []
    llm_events: list[NewEvent] = []

    if llm is not None:
        logger.info("[workflow] running LLM extraction...")
        r_results = await asyncio.gather(
            extract_restaurants_from_articles(llm, eater_articles),
            extract_restaurants_from_articles(llm, ddg_restaurant_articles),
            return_exceptions=True,
        )
        for r in r_results:
            llm_restaurants.extend(_settled(r, "LLM restaurants", []))

        e_results = await asyncio.gather(
            extract_events_from_articles(llm, ddg_event_articles),
            return_exceptions=True,
        )
        for e in e_results:
            llm_events.extend(_settled(e, "LLM events", []))

        logger.info(
            "[workflow] LLM extracted: %d restaurants, %d events",
            len(llm_restaurants),
            len(llm_events),
        )

    restaurants = dedup_restaurants(
        [*sfist_items, *michelin_items, *llm_restaurants]
    )
    events_list = dedup_events(
        [*funcheap_events, *famsf_events, *cal_academy_events, *llm_events]
    )

    logger.info(
        "[workflow] candidates: %d restaurants, %d events",
        len(restaurants),
        len(events_list),
    )

    if restaurants or events_list:
        await apply_discovered_items(
            restaurants=[asdict(r) for r in restaurants],
            events=[asdict(e) for e in events_list],
        )
    else:
        logger.info("[workflow] nothing new")

    return {"restaurants": len(restaurants), "events": len(events_list)}
