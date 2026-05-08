# SF Pulse

SF Pulse tracks new San Francisco restaurant openings and local events. It's a FastAPI + asyncpg + Render Workflows reference app showcasing the [Render Python SDK](https://github.com/render-oss/sdk/tree/main/python).

The interactive workflow diagram is preserved as a small Vite + React sub-project (`web/diagram/`) and served as a static bundle at `/diagram/`.

## Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Frender-examples%2Fsf-pulse-python-workshop)

`render.yaml` provisions:

- **Web** (`sf-pulse-python`): FastAPI app, runs migrations pre-deploy, starts via `uvicorn`. Health check at `/api/healthz`.
- **Cron** (`sf-pulse-python-daily`): runs daily at 7 AM PDT. Triggers the daily-refresh workflow via the Render Python SDK.
- **Database** (`sf-pulse-python-db`): PostgreSQL.
- **Key-value** (`sf-pulse-python-realtime`): Redis for cross-instance SSE fanout.

The workflow worker service (`sf-pulse-python-workflow`) is created manually in the Dashboard — Render Workflows are not yet first-class in Blueprint YAML. See [docs/workflow-setup.md](docs/workflow-setup.md).

### Step 1: Create the `sf-pulse-python-env` env group

Dashboard → **Env Groups** → **New Env Group** → name it `sf-pulse-python-env`.

| Variable | Value |
| --- | --- |
| `LLM_API_KEY` | Your OpenAI or Anthropic API key (required for full extraction) |
| `LLM_PROVIDER` | _(optional)_ `openai` or `anthropic` — auto-detected from key prefix if omitted |
| `LLM_MODEL` | _(optional)_ e.g. `gpt-4o-mini` |
| `VAPID_PUBLIC_KEY` | _(optional)_ required only for push notifications |
| `VAPID_PRIVATE_KEY` | _(optional)_ required only for push notifications |
| `VAPID_SUBJECT` | _(optional)_ `mailto:you@example.com` |
| `APP_URL` | _(optional)_ public URL for RSS / push payloads |

### Step 2: Create the workflow service manually

1. Dashboard → **New** → **Workflow** → connect the repo, branch `main`.
2. Name: `sf-pulse-python-workflow`.
3. Build Command: `pip install --upgrade uv && uv sync --frozen`
4. Start Command: `uv run python -m workflow.main`
5. Plan: Starter.
6. Add the `sf-pulse-python-env` env group.
7. Save & deploy. Note the **Slug** in Settings — you'll need it for `SF_PULSE_WORKFLOW_SLUG`.

### Step 3: Deploy the Blueprint

Click the Deploy button above (or `New` → `Blueprint` against your fork). The Blueprint provisions web + cron + Postgres + Redis.

After the first deploy:

1. Copy `DATABASE_URL` from the `sf-pulse-python-db` database and `REDIS_URL` from `sf-pulse-python-realtime`, set them on the env group.
2. On the `sf-pulse-python-daily` cron service, set:

| Variable | How to get it |
| --- | --- |
| `RENDER_API_KEY` | Dashboard → Account Settings → API Keys → Create API Key |
| `SF_PULSE_WORKFLOW_SLUG` | Slug from `sf-pulse-python-workflow` Settings (step 2) |

### Step 4: Verify

1. `sf-pulse-python` web service: open the URL — home page should render.
2. `sf-pulse-python-daily`: **Trigger Run** in Dashboard.
3. `sf-pulse-python-workflow`: logs should show all tasks execute.
4. Refresh the home page — restaurants should appear.

## Stack

- Python 3.12+
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- [asyncpg](https://magicstack.github.io/asyncpg/) (raw SQL, no ORM)
- [Pydantic v2](https://docs.pydantic.dev/) for request/response validation
- [httpx](https://www.python-httpx.org/) + [selectolax](https://github.com/rushter/selectolax) for scraping
- [openai](https://github.com/openai/openai-python) and [anthropic](https://github.com/anthropics/anthropic-sdk-python) Python SDKs (provider-agnostic LLM extraction)
- [Render Python SDK](https://github.com/render-oss/sdk/tree/main/python) for workflows
- [pywebpush](https://github.com/web-push-libs/pywebpush) for web push
- [redis-py](https://redis.readthedocs.io/) async + [sse-starlette](https://github.com/sysid/sse-starlette) for realtime
- React + Vite for the workflow diagram (kept verbatim from the TS repo)
- `uv` for package management

## Repo layout

```
app/
  main.py                # FastAPI factory + lifespan
  config.py              # pydantic-settings (env vars)
  db.py                  # asyncpg pool singleton
  storage.py             # data access (restaurants/subs/data_updates)
  refresh.py             # apply discovered items + push fan-out
  sse.py                 # SSE broadcaster (Redis pub/sub or in-process)
  push.py                # pywebpush + VAPID
  security.py            # x-cron-secret + Pydantic schemas
  routes/                # FastAPI routers (api_*, pages.py)
  shared/                # pure utilities (types, dates, identity, filters, ...)
  llm/                   # provider-agnostic LLM extraction
  sources/               # source scrapers (eater, sfist, michelin, ddg)
  templates/             # Jinja2 templates
workflow/                # Render Workflows worker
  main.py
  tasks/                 # one module per task
bin/
  migrate.py             # python -m bin.migrate
  trigger_workflow.py    # cron service entrypoint
migrations/              # plain SQL (0001-0011), copied verbatim from sf-pulse-ts
static/
  diagram/               # Vite build output (gitignored, built during deploy)
  styles/, icons/, home.js, map.js, service-worker.js, manifest.webmanifest
web/diagram/             # Vite + React sub-project for the workflow diagram
tests/                   # pytest suite (testcontainers Postgres)
docs/                    # architecture, workflow setup, deployment
render.yaml              # Render Blueprint
```

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 18+ (only for the `web/diagram/` build)
- PostgreSQL (or Docker for testcontainers when running tests)
- Redis (optional; used for cross-instance SSE)

## Local development

```sh
# 1. Install Python deps
uv sync

# 2. Build the React diagram (one-time; rebuild on changes)
cd web/diagram && npm ci && npm run build && cd ../..

# 3. Configure environment
cp .env.example .env.local   # fill in DATABASE_URL, optional LLM_API_KEY, optional VAPID_*

# 4. Run migrations
uv run python -m bin.migrate

# 5. Start the dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>.

### Trigger an initial data load

```sh
# Seed local Postgres directly — no Workflows runtime required:
uv run python -c "import asyncio; from app.refresh import run_daily_refresh; asyncio.run(run_daily_refresh())"
```

Set `LLM_API_KEY` for full coverage; without it only the regex sources (SFist, Michelin) produce results.

To exercise the Render Workflows runtime locally instead, run `render workflows dev -- python -m workflow.main` and trigger `daily-refresh` from a second terminal — see [`docs/workflow-setup.md`](docs/workflow-setup.md).

## Tests

```sh
uv run pytest -q
```

Tests use [testcontainers-python](https://testcontainers-python.readthedocs.io/) — they spin up a real PostgreSQL container per session, so **Docker must be running**. Pure-utility tests (dates, html, identity, etc.) run without Docker.

## Environment variables

| Variable | Where used | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | web, cron, workflow | PostgreSQL connection string |
| `REDIS_URL` | web | Redis pub/sub for multi-instance SSE (optional) |
| `CRON_SECRET` | web | Required header on protected mutation endpoints |
| `APP_URL` / `RENDER_EXTERNAL_URL` | web | Public URL used in RSS feed / push payloads |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | web, workflow | Web push (optional) |
| `LLM_API_KEY` | workflow | OpenAI or Anthropic key — without it, only regex sources produce results |
| `LLM_PROVIDER` | workflow | `openai` or `anthropic`; auto-detected if blank |
| `LLM_MODEL` | workflow | Model override |
| `RENDER_API_KEY` | cron | Used by `bin/trigger_workflow.py` to start the daily workflow |
| `SF_PULSE_WORKFLOW_SLUG` | cron | Slug of the workflow service in Render |

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Home page (Jinja2) |
| GET | `/map` | Neighborhood map view |
| GET | `/diagram/` | React workflow diagram (static bundle) |
| GET | `/restaurants/{id}` | Restaurant detail |
| GET | `/api/healthz` | Health check |
| GET | `/api/restaurants` | List visible restaurants |
| GET | `/api/restaurants/{id}` | Restaurant by id |
| DELETE | `/api/restaurants/{id}` | Delete (requires `x-cron-secret`) |
| GET | `/api/events-stream` | SSE realtime updates |
| GET | `/api/updates` | Recent data update log |
| GET | `/api/updates/last-updated` | Latest update timestamp |
| GET | `/api/rss.xml` | RSS feed |
| GET | `/api/push/vapid-key` | VAPID public key |
| POST | `/api/push/subscribe` | Register push subscription |
| GET | `/api/push/subscription?endpoint=...` | Look up a subscription |
| POST | `/api/push/preferences` | Update push filter preferences |
| POST | `/api/push/unsubscribe` | Remove a subscription |

## Documentation

- [docs/architecture.md](docs/architecture.md) — system overview and data flow
- [docs/workflow-setup.md](docs/workflow-setup.md) — Workflow worker setup
- [docs/deployment.md](docs/deployment.md) — full deploy walkthrough
- [docs/openai-api-permissions.md](docs/openai-api-permissions.md) — required OpenAI key permissions

## License

MIT
