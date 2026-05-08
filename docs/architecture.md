# Architecture

## Component overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Render Workflow                            │
│                                                                      │
│   sf-pulse-python-daily (cron)  ───▶  sf-pulse-python-workflow       │
│   (triggers via Render SDK)            (runs Python tasks)           │
│                                                                      │
│   daily_refresh orchestrator                                         │
│     ├── fetch_eater_sf       ──▶ list[RawArticle]                    │
│     ├── fetch_sfist          ──▶ list[NewRestaurant] (regex)         │
│     ├── fetch_michelin       ──▶ list[NewRestaurant] (regex)         │
│     ├── search_restaurants   ──▶ list[RawArticle] (DDG)              │
│     │                                                                │
│     ▼                                                                │
│   LLM extraction (OpenAI/Anthropic) — articles → structured items    │
│     ▼                                                                │
│   apply_discovered_items                                             │
│     ├── deduplicate                                                  │
│     ├── upsert (Postgres ON CONFLICT)                                │
│     ├── broadcast SSE event ─────────┐                               │
│     └── push to subscribers ──┐      │                               │
└───────────────────────────────┼──────┼────────────────────────────────┘
                                │      │
                                ▼      ▼
                          ┌────────────────────────────┐
                          │      sf-pulse-python       │
                          │      (FastAPI web)         │
                          │                            │
                          │  /            (Jinja2)     │
                          │  /api/*       (JSON)       │
                          │  /api/events-stream (SSE)  │
                          │  /diagram/*   (Vite/React) │
                          └────────────────────────────┘
                                │      │
                                ▼      ▼
                          ┌──────────┐ ┌──────────┐
                          │ Postgres │ │  Redis   │
                          │ (sf-...-db) │ │ (sf-...-realtime) │
                          └──────────┘ └──────────┘
```

## Source modules

Each scraper in `app.sources` produces either `list[NewRestaurant]` directly (regex sources: SFist, Michelin) or `list[RawArticle]` for the LLM pipeline to extract from (Eater SF, DuckDuckGo).

## LLM extraction

`app.llm.pipeline.extract_restaurants_from_articles` batches articles into ~12K-character chunks, sends each batch to the configured provider (OpenAI via `chat.completions.parse` with a Pydantic `response_format`, or Anthropic via tool-use), and merges results.

The provider is auto-detected from the `LLM_API_KEY` prefix (`sk-ant-` → Anthropic, else OpenAI) unless `LLM_PROVIDER` is explicitly set.

If `LLM_API_KEY` is not configured, the factory returns `None` and the pipeline emits an empty list — callers continue with regex-only sources.

## Deduplication

- **Restaurants**: `identity_key = lower(name) | (lower(address) || lower(neighborhood))`. ON CONFLICT (identity_key) updates fields.
- `app.refresh` also has fuzzier matching strategies for "near-miss" duplicates (e.g. address normalization, source-URL match) before falling back to identity-key match.

## Realtime

- `app.sse.broadcast(event, data)` publishes to Redis (`sf-pulse:realtime` channel) when `REDIS_URL` is set, falling back to in-process fan-out otherwise.
- The `/api/events-stream` endpoint creates a per-client async queue. Heartbeats every 25 seconds.
- The browser receives `restaurants` events with `{version, upserted, deleted, summary}` payloads. The current `static/home.js` does a soft reload after a brief debounce; a future enhancement could splice rows in place.

## Push notifications

- VAPID keys live in `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`. If unset, the push fan-out is silently skipped.
- After `apply_discovered_items` finishes, only subscribers whose preferences match the new items receive a push (`restaurant_matches_push_preferences`).
- Push provider endpoints are restricted to a trusted hostname allowlist (`is_trusted_push_endpoint`).
