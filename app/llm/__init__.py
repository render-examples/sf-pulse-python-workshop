"""LLM extraction module — port of server/llm/index.ts.

Public surface:
- get_llm_client(): factory reading config; returns None when no API key.
- create_llm_client(): explicit construction.
- extract_structured(): single-call wrapper with one-shot retry.
- extract_restaurants_from_articles(): batched pipeline.
- set_llm_client_for_tests(): test injection hook.
"""

from __future__ import annotations

from typing import Literal

from app.config import get_settings
from app.llm.extract import LLMClient, extract_structured
from app.llm.pipeline import extract_restaurants_from_articles
from app.llm.providers.anthropic_provider import create_anthropic_client
from app.llm.providers.openai_provider import create_openai_client
from app.llm.schemas import (
    RESTAURANT_EXTRACTION_PROMPT,
    RawArticle,
    RestaurantExtraction,
)

__all__ = [
    "LLMClient",
    "RESTAURANT_EXTRACTION_PROMPT",
    "RawArticle",
    "RestaurantExtraction",
    "create_llm_client",
    "extract_restaurants_from_articles",
    "extract_structured",
    "get_llm_client",
    "set_llm_client_for_tests",
]

Provider = Literal["openai", "anthropic"]

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}

_client_override: LLMClient | None = None


def set_llm_client_for_tests(client: LLMClient | None) -> None:
    global _client_override
    _client_override = client


def _detect_provider(api_key: str, configured: str) -> Provider:
    if configured:
        normalized = configured.strip().lower()
        if normalized in ("openai", "anthropic"):
            return normalized  # type: ignore[return-value]
    return "anthropic" if api_key.startswith("sk-ant-") else "openai"


def create_llm_client(
    *, provider: Provider, api_key: str, model: str | None = None
) -> LLMClient:
    resolved_model = model or DEFAULT_MODELS.get(provider) or "gpt-4o-mini"
    if provider == "openai":
        return create_openai_client(api_key, resolved_model)
    if provider == "anthropic":
        return create_anthropic_client(api_key, resolved_model)
    raise ValueError(f"Unknown LLM provider: {provider}")


def get_llm_client() -> LLMClient | None:
    if _client_override is not None:
        return _client_override

    settings = get_settings()
    api_key = settings.llm_api_key
    if not api_key:
        return None

    provider = _detect_provider(api_key, settings.llm_provider)
    model = settings.llm_model or None
    return create_llm_client(provider=provider, api_key=api_key, model=model)
