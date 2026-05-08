"""RSS feed — port of src/server/api/rss.ts."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime

from fastapi import APIRouter, Response

from app import storage
from app.security import get_public_app_url
from app.shared.html import escape_html

router = APIRouter(tags=["rss"])


def _xml_escape(value: str) -> str:
    return escape_html(value)


def _to_rfc822(dt: datetime) -> str:
    return format_datetime(dt.astimezone(UTC))


@router.get("/api/rss.xml", response_class=Response)
async def rss_xml() -> Response:
    app_url = get_public_app_url()
    restaurants = await storage.get_restaurants()

    items: list[dict] = []
    for r in restaurants:
        desc_parts = [
            r.cuisine,
            r.neighborhood,
            r.address,
            f"Opened: {r.opened_date}" if r.opened_date else None,
        ]
        items.append(
            {
                "title": f"New restaurant: {r.name}",
                "link": r.source_url or app_url,
                "description": " · ".join(p for p in desc_parts if p),
                "pubDate": _to_rfc822(r.added_at),
                "guid": f"{app_url}/restaurants/{r.id}",
            }
        )

    items.sort(key=lambda i: i["pubDate"], reverse=True)
    items = items[:50]

    items_xml = "".join(
        f"""
    <item>
      <title>{_xml_escape(i["title"])}</title>
      <link>{_xml_escape(i["link"])}</link>
      <description>{_xml_escape(i["description"])}</description>
      <pubDate>{i["pubDate"]}</pubDate>
      <guid isPermaLink="false">{_xml_escape(i["guid"])}</guid>
    </item>"""
        for i in items
    )

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>SF Pulse</title>
    <link>{_xml_escape(app_url)}</link>
    <description>New SF restaurant openings</description>
    <language>en-us</language>
    <atom:link href="{_xml_escape(app_url + "/api/rss.xml")}" rel="self" type="application/rss+xml" />
    <lastBuildDate>{_to_rfc822(datetime.now(UTC))}</lastBuildDate>
    {items_xml}
  </channel>
</rss>"""
    return Response(content=body, media_type="application/rss+xml; charset=utf-8")
