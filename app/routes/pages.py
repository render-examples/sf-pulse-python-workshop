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
    get_restaurant_cuisine_options,
    get_restaurant_neighborhood_options,
)
from app.shared.timeline import build_timeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    build_timeline=build_timeline,
)

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    initial = await get_initial_data()
    restaurants = initial.restaurants
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "SF Pulse",
            "restaurants": restaurants,
            "last_updated": initial.last_updated,
            "restaurant_neighborhoods": get_restaurant_neighborhood_options(restaurants),
            "restaurant_cuisines": get_restaurant_cuisine_options(restaurants),
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
        },
    )


@router.get("/restaurants/{id}", response_class=HTMLResponse)
async def restaurant_detail(id: int, request: Request) -> HTMLResponse:
    row = await storage.get_restaurant_by_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    visible_restaurants = await storage.get_visible_restaurants()
    related_restaurants = [
        item
        for item in visible_restaurants
        if item.id != row.id
        and (item.neighborhood == row.neighborhood or item.cuisine == row.cuisine)
    ][:4]
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
            "map_query": map_query,
        },
    )
