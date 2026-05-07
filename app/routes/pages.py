"""HTML page routes — Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    derive_event_category=derive_event_category,
    derive_event_neighborhood=derive_event_neighborhood,
    format_event_category=format_event_category,
    build_timeline=build_timeline,
)

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    initial = await get_initial_data()
    restaurants = initial.restaurants
    events = initial.events
    context = {
        "request": request,
        "title": "SF Pulse",
        "restaurants": restaurants,
        "events": events,
        "last_updated": initial.last_updated,
        "restaurant_neighborhoods": get_restaurant_neighborhood_options(restaurants),
        "restaurant_cuisines": get_restaurant_cuisine_options(restaurants),
        "event_neighborhoods": get_event_neighborhood_options(events),
        "event_categories": get_event_category_options(events),
        "initial_data_json": serialize_for_inline_script(initial.model_dump(by_alias=True, mode="json")),
        "app_url": get_public_app_url(),
    }
    return templates.TemplateResponse("index.html", context)


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request) -> HTMLResponse:
    initial = await get_initial_data()
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
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
    return templates.TemplateResponse(
        "restaurant_detail.html",
        {"request": request, "title": row.name, "restaurant": row},
    )


@router.get("/events/{id}", response_class=HTMLResponse)
async def event_detail(id: int, request: Request) -> HTMLResponse:
    row = await storage.get_event_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return templates.TemplateResponse(
        "event_detail.html",
        {"request": request, "title": row.title, "event": row},
    )
