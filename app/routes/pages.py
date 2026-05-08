"""HTML page routes — Jinja2 templates."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import storage
from app.routes.utils import get_initial_data
from app.security import get_public_app_url, serialize_for_inline_script
from app.shared.catalog import (
    derive_event_category,
    derive_event_neighborhood,
    format_event_category,
    get_event_category_options,
    get_event_neighborhood_options,
    get_restaurant_cuisine_options,
    get_restaurant_neighborhood_options,
)
from app.shared.timeline import build_timeline
from app.shared.types import SFEvent

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    build_timeline=build_timeline,
    derive_event_category=derive_event_category,
    derive_event_neighborhood=derive_event_neighborhood,
    format_event_category=format_event_category,
)

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    initial = await get_initial_data()
    restaurants = initial.restaurants
    events = initial.events
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "SF Pulse",
            "restaurants": restaurants,
            "events": events,
            "last_updated": initial.last_updated,
            "restaurant_neighborhoods": get_restaurant_neighborhood_options(restaurants),
            "restaurant_cuisines": get_restaurant_cuisine_options(restaurants),
            "event_neighborhoods": get_event_neighborhood_options(events),
            "event_categories": get_event_category_options(events),
            "initial_data_json": serialize_for_inline_script(
                initial.model_dump(by_alias=True, mode="json")
            ),
            "app_url": get_public_app_url(),
        },
    )


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request) -> HTMLResponse:
    initial = await get_initial_data()
    return templates.TemplateResponse(
        request,
        "map.html",
        {
            "title": "SF Pulse — Map",
            "restaurants": initial.restaurants,
            "events": initial.events,
        },
    )


@router.get("/restaurants/{id}", response_class=HTMLResponse)
async def restaurant_detail(id: int, request: Request) -> HTMLResponse:
    row = await storage.get_restaurant_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    visible_restaurants = await storage.get_visible_restaurants()
    visible_events = [
        SFEvent.model_validate(e.model_dump())
        for e in await storage.get_visible_events()
    ]
    related_restaurants = [
        item
        for item in visible_restaurants
        if item.id != row.id
        and (item.neighborhood == row.neighborhood or item.cuisine == row.cuisine)
    ][:4]
    nearby_events = [
        event
        for event in visible_events
        if derive_event_neighborhood(event) == row.neighborhood
    ][:5]
    map_query = (
        f"https://www.google.com/maps/search/?api=1&query={quote(row.address)}"
        if row.address
        else None
    )
    return templates.TemplateResponse(
        request,
        "restaurant_detail.html",
        {
            "title": f"{row.name} — SF Pulse",
            "restaurant": row,
            "related_restaurants": related_restaurants,
            "nearby_events": nearby_events,
            "map_query": map_query,
        },
    )


@router.get("/events/{id}", response_class=HTMLResponse)
async def event_detail(id: int, request: Request) -> HTMLResponse:
    row = await storage.get_event_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event_public = SFEvent.model_validate(row.model_dump())
    category = derive_event_category(event_public)
    neighborhood = derive_event_neighborhood(event_public)
    visible_events = [
        SFEvent.model_validate(e.model_dump())
        for e in await storage.get_visible_events()
    ]
    visible_restaurants = await storage.get_visible_restaurants()
    related_events = [
        item
        for item in visible_events
        if item.id != row.id and derive_event_neighborhood(item) == neighborhood
    ][:5]
    related_restaurants = [
        r for r in visible_restaurants if r.neighborhood == neighborhood
    ][:5]
    map_query = (
        f"https://www.google.com/maps/search/?api=1&query={quote(row.location)}"
        if row.location
        else None
    )
    return templates.TemplateResponse(
        request,
        "event_detail.html",
        {
            "title": f"{row.title} — SF Pulse",
            "event": row,
            "category": category,
            "category_label": format_event_category(category),
            "neighborhood": neighborhood,
            "related_events": related_events,
            "related_restaurants": related_restaurants,
            "map_query": map_query,
        },
    )
