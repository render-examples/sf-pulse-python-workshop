# AGENTS.md

Guidance for AI agents (and humans) working in this codebase.

## What this is

SF Pulse Python is a FastAPI port of the original TypeScript app at [`render-examples/sf-pulse-ts`](https://github.com/render-examples/sf-pulse-ts). It tracks SF restaurant openings.

This repo is also a GitHub template for the **Should Agents Be Durable?** workshop at AI Council. Workshop attendees extend the durable Render Workflows pipeline with an SF events feature. The implementation spec for that exercise lives in [`demo_prompt.md`](demo_prompt.md); follow it verbatim when asked to "add the Events feature."

It uses:

- FastAPI + Jinja2 templates for HTML pages and JSON APIs
- asyncpg + plain SQL migrations
- Render Workflows (Python SDK) for the daily scraping pipeline
- LLM-based extraction (OpenAI or Anthropic) with regex fallback
- Web push + SSE realtime
- A small React + Vite sub-project at `web/diagram/` for the workflow visualization (kept verbatim from the TS repo)

## Core principles

- **PostgreSQL is the source of truth.** Never rewrite application SQL or behavior to work around test infrastructure.
- **Tests use real Postgres.** The test suite spins up an actual PostgreSQL container via [testcontainers-python](https://testcontainers-python.readthedocs.io/). No mocks, no fakes for the database layer. If a feature works in pg-mem-style mocks but breaks against real Postgres, that's a real bug.
- **Tests are mandatory.** Every feature, bug fix, or behavior change must include or update tests.

## Architecture

**Web service** (`uvicorn app.main:app`):
- Renders HTML pages from Jinja2 templates (home, map, detail pages, diagram iframe shell)
- Exposes JSON API at `/api/*`
- Streams realtime updates via SSE (Redis pub/sub when `REDIS_URL` is set; in-process fallback otherwise)
- Sends web push notifications via pywebpush

**Workflow service** (`python -m workflow.main`):
- Registers tasks via `@app.task` decorators on the `Workflows()` instance defined in `workflow/_app.py`
- The `daily_refresh` orchestrator fans out to source-fetch tasks via `asyncio.gather`, runs LLM extraction conditionally, dedupes, and calls `apply_discovered_items`
- Each source task is a thin wrapper around an `app.sources.*` function

**Cron job** (`python -m bin.trigger_workflow`):
- Uses the Render Python SDK (`Render` client) to start the `daily-refresh` task by slug
- Polls until completion. Exits 0 on success, 1 on failure.

**Database**:
- Plain SQL migrations in `migrations/` (numeric prefix). Migrations copied verbatim from sf-pulse-ts and are standard PostgreSQL.
- `bin/migrate.py` runs them. Tracked in `schema_migrations`. Idempotent.

**Realtime**:
- `app.sse` exposes `broadcast(event, data)` and an `EventSourceResponse` stream.
- When `REDIS_URL` is set, broadcasts go to a Redis pub/sub channel `sf-pulse:realtime` so multiple web service instances see each other's events. The managed Render product backing this is Render Key Value (Valkey), which is Redis-compatible.

**LLM extraction**:
- `app.llm` is provider-agnostic. The factory (`get_llm_client()`) auto-detects from `LLM_API_KEY` (`sk-ant-` prefix means Anthropic, otherwise OpenAI) or from `LLM_PROVIDER`.
- Returns `None` gracefully when no API key is set. Callers degrade to regex-only extraction (SFist and Michelin still produce results).

For a deeper "why each component exists" walkthrough plus the daily-refresh sequence diagram, see [`docs/architecture.md`](docs/architecture.md).

## Code conventions

- **Python 3.12+**, `from __future__ import annotations` at the top of every module.
- **Pydantic v2** for request/response models, validators, and settings.
- **asyncpg** with parameterized queries (`$1`, `$2`, …). Never f-string SQL.
- **Logging**: `logging.getLogger(__name__)`. INFO for lifecycle, WARNING for degraded states, ERROR for failures. Use stable prefixes like `[migrate]`, `[realtime]`, `[push]`.
- **No comments** unless something is genuinely non-obvious. Don't explain WHAT; well-named identifiers do that.
- **Type hints everywhere.** Pyright runs in CI.
- **Ruff** for lint (config in `pyproject.toml`).
- **No semicolons** (Python doesn't use them; this matches the original TS Prettier config aesthetically too).

## Storage layer

`app.storage` accepts an optional `pool` keyword argument on every function for test injection. ON CONFLICT upserts use `identity_key` (restaurants) to prevent duplicates.

## Migrations

Plain SQL files in `migrations/`. Each runs in a single transaction. Must be:
- **Idempotent**: use `IF NOT EXISTS`, `ON CONFLICT`, `WHERE NOT EXISTS` guards
- **Standard PostgreSQL**: no testcontainer-specific workarounds

Run `uv run pytest tests/test_migrate.py` before the full suite when editing migrations.

## Security

- Mutation endpoints require `x-cron-secret` header matching `CRON_SECRET`.
- Push endpoints validate trusted provider hostnames (`fcm.googleapis.com`, `*.push.apple.com`, and so on). See `app.security.is_trusted_push_endpoint`.
- All user input goes through Pydantic schemas in `app.security` or directly on FastAPI route handlers.

## Documentation

When adding or changing features, update:
- `README.md` for user-facing setup, workshop steps, and env vars
- `AGENTS.md` for architecture and conventions
- `docs/architecture.md` for non-trivial structural changes
- `docs/deployment.md` for deploy-related changes

## Environment

Local secrets go in `.env.local` (gitignored). Only `DATABASE_URL` is required for the app to boot. Tests don't need any env vars (they spin up their own Postgres).

For full LLM extraction set `LLM_API_KEY`. For push notifications set `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`.

## Local runtime

Two supported flows for running the app outside Render:

- **Docker Compose** (preferred for the workshop): `docker compose up --build` brings up Postgres, Valkey, and the FastAPI app with migrations applied. The app is at <http://localhost:8000>. Postgres and Valkey are exposed on `localhost:5432` and `localhost:6379` so `render workflows dev` on the host can connect to them. See `compose.yaml` and `Dockerfile`.
- **Native uv**: `uv sync && uv run python -m bin.migrate && uv run uvicorn app.main:app --reload`. Requires a local Postgres install.

When implementing workshop changes, prefer the Docker Compose flow so the agent's setup matches the attendee's.
