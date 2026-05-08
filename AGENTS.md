# AGENTS.md

Guidance for AI agents (and humans) working in this codebase.

## Core principles

- **PostgreSQL is the source of truth.** Never rewrite application SQL or behavior to work around test infrastructure.
- **Tests use real Postgres.** The test suite spins up an actual PostgreSQL container via [testcontainers-python](https://testcontainers-python.readthedocs.io/). No mocks, no fakes for the database layer. If a feature works in pg-mem-style mocks but breaks against real Postgres, that's a real bug.
- **Tests are mandatory.** Every feature, bug fix, or behavior change must include or update tests.

## What this is

SF Pulse Python is a FastAPI port of the original TypeScript app at [`render-examples/sf-pulse-ts`](https://github.com/render-examples/sf-pulse-ts). It tracks SF restaurant openings and local events. It uses:

- FastAPI + Jinja2 templates for HTML pages and JSON APIs
- asyncpg + plain SQL migrations
- Render Workflows (Python SDK) for the daily scraping pipeline
- LLM-based extraction (OpenAI or Anthropic) with regex fallback
- Web push + SSE realtime
- A small React + Vite sub-project at `web/diagram/` for the workflow visualization (kept verbatim from the TS repo)

## Architecture

**Web service** (`uvicorn app.main:app`):
- Renders HTML pages from Jinja2 templates (home, map, detail pages, diagram iframe shell)
- Exposes JSON API at `/api/*`
- Streams realtime updates via SSE (Redis pub/sub when `REDIS_URL` is set; in-process fallback otherwise)
- Sends web push notifications via pywebpush

**Workflow worker** (`python -m workflow.main`):
- Registers tasks via `@app.task` decorators on the `Workflows()` instance defined in `workflow/_app.py`
- The `daily_refresh` orchestrator fans out to source-fetch tasks via `asyncio.gather`, runs LLM extraction conditionally, dedupes, and calls `apply_discovered_items`
- Each source task is a thin wrapper around an `app.sources.*` function

**Cron service** (`python -m bin.trigger_workflow`):
- Uses the Render Python SDK (`Render` client) to start the `daily-refresh` task by slug
- Polls until completion; exits 0 on success, 1 on failure

**Database**:
- Plain SQL migrations in `migrations/` (numeric prefix). Migrations copied verbatim from sf-pulse-ts — they're standard PostgreSQL.
- `bin/migrate.py` runs them; tracked in `schema_migrations`. Idempotent.

**Realtime**:
- `app.sse` exposes `broadcast(event, data)` and an `EventSourceResponse` stream.
- When `REDIS_URL` is set, broadcasts go to a Redis pub/sub channel `sf-pulse:realtime` so multiple instances see each other's events.

**LLM extraction**:
- `app.llm` is provider-agnostic. The factory (`get_llm_client()`) auto-detects from `LLM_API_KEY` (`sk-ant-` → Anthropic, otherwise OpenAI) or from `LLM_PROVIDER`.
- Returns `None` gracefully when no API key is set — callers degrade to regex-only extraction (SFist + Michelin still produce results).

## Code conventions

- **Python 3.12+**, `from __future__ import annotations` at the top of every module.
- **Pydantic v2** for request/response models, validators, and settings.
- **asyncpg** with parameterized queries (`$1`, `$2`, …). Never f-string SQL.
- **Logging**: `logging.getLogger(__name__)`. INFO for lifecycle, WARNING for degraded states, ERROR for failures. Use stable prefixes like `[migrate]`, `[realtime]`, `[push]`.
- **No comments** unless something is genuinely non-obvious. Don't explain WHAT — well-named identifiers do that.
- **Type hints everywhere.** Pyright runs in CI.
- **Ruff** for lint (config in `pyproject.toml`).
- **No semicolons** (Python doesn't use them; this matches the original TS Prettier config aesthetically too).

## Storage layer

`app.storage` accepts an optional `pool` keyword argument on every function for test injection. ON CONFLICT upserts use `identity_key` (restaurants) and `dedupe_key` (events) to prevent duplicates.

## Migrations

Plain SQL files in `migrations/`. Each runs in a single transaction. Must be:
- **Idempotent**: use `IF NOT EXISTS`, `ON CONFLICT`, `WHERE NOT EXISTS` guards
- **Standard PostgreSQL**: no testcontainer-specific workarounds

Run `uv run pytest tests/test_migrate.py` before the full suite when editing migrations.

## Security

- Mutation endpoints require `x-cron-secret` header matching `CRON_SECRET`.
- Push endpoints validate trusted provider hostnames (`fcm.googleapis.com`, `*.push.apple.com`, etc.) — see `app.security.is_trusted_push_endpoint`.
- All user input goes through Pydantic schemas in `app.security` or directly on FastAPI route handlers.

## Documentation

When adding or changing features, update:
- `README.md` — user-facing setup, API surface, env vars
- `AGENTS.md` — architecture, conventions
- `docs/architecture.md` — for non-trivial structural changes
- `docs/workflow-setup.md` and `docs/deployment.md` — for deploy-related changes

## Environment

Local secrets go in `.env.local` (gitignored). Only `DATABASE_URL` is required for the app to boot. Tests don't need any env vars (they spin up their own Postgres).

For full LLM extraction set `LLM_API_KEY`; for push notifications set `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`.
