"""Batched article extraction pipeline — port of server/llm/pipeline.ts."""

from __future__ import annotations

from app.llm.extract import LLMClient, extract_structured
from app.llm.schemas import (
    RESTAURANT_EXTRACTION_PROMPT,
    RawArticle,
    RestaurantExtraction,
)
from app.storage import NewRestaurant

MAX_BATCH_CHARS = 12_000


def _batch_articles(articles: list[RawArticle]) -> list[list[RawArticle]]:
    batches: list[list[RawArticle]] = []
    current: list[RawArticle] = []
    current_size = 0

    for article in articles:
        article_size = len(article.body_text) + len(article.title) + 100
        if current and current_size + article_size > MAX_BATCH_CHARS:
            batches.append(current)
            current = []
            current_size = 0
        current.append(article)
        current_size += article_size

    if current:
        batches.append(current)

    return batches


def _format_article_batch(articles: list[RawArticle]) -> str:
    if len(articles) == 1:
        a = articles[0]
        pub = a.pub_date or "unknown"
        return f"Title: {a.title}\nURL: {a.url}\nPublished: {pub}\n\n{a.body_text}"

    return "\n\n".join(
        f'<article url="{a.url}">\nTitle: {a.title}\nPublished: {a.pub_date or "unknown"}\n\n{a.body_text}\n</article>'
        for a in articles
    )


async def extract_restaurants_from_articles(
    client: LLMClient, articles: list[RawArticle]
) -> list[NewRestaurant]:
    if not articles:
        return []

    results: list[NewRestaurant] = []
    for batch in _batch_articles(articles):
        source_url = batch[0].url if len(batch) == 1 else None
        extraction = await extract_structured(
            client,
            schema=RestaurantExtraction,
            prompt=RESTAURANT_EXTRACTION_PROMPT,
            text=_format_article_batch(batch),
        )
        if extraction is None:
            continue
        for r in extraction.restaurants:
            results.append(
                NewRestaurant(
                    name=r.name,
                    neighborhood=r.neighborhood,
                    cuisine=r.cuisine,
                    opened_date=r.opened_date,
                    address=r.address,
                    source_url=source_url,
                )
            )

    return results
