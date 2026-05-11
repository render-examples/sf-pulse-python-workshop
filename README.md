# SF Pulse Workshop Companion Repo

This is the companion repo for the **Should Agents Be Durable?** workshop hosted at AI Council. It's a GitHub template. Click **Use this template** above to create your own copy, then follow the steps below.

By the end of the workshop, you'll have shipped a durable agent: not a one-off prompt, but a repeatable Render Workflows pipeline that you ran locally, extended with new tasks, and redeployed.

## What you'll build

You'll work with SF Pulse, a FastAPI app whose agent behavior is a durable Render Workflows pipeline. Today the pipeline runs a daily refresh task that discovers new SF restaurant openings, normalizes candidates, deduplicates them, and writes the results to Render Postgres.

You'll extend that pipeline rather than write a one-off script. Adding an Events feature is the concrete exercise: new source tasks, a broader orchestrator, the same deduplication and persistence path. By the end, `daily-refresh` should fan out across both restaurant and event sources, and the web app should show an Events tab backed by data from your database.

## What you'll learn

- How to split an agent workflow into retryable tasks
- How to fan out across multiple sources and fan in normalized results
- How to treat an LLM as one stage in a durable pipeline, not the whole system
- How to use Postgres as the source of truth for discovered data
- How to run and inspect workflow tasks locally before deploying

## Workshop steps

### 1. Create your workshop repo

Create your own public GitHub repo from this template. Use this repo for the rest of the workshop so Render and your local machine point at the same codebase.

1. Click **Use this template** at the top of this repo.
2. Name the repo `sf-pulse-python-workshop-<firstname-lastname>`.
3. Set the repo visibility to Public. A public repo lets you add it to the workshop Render workspace without connecting your GitHub profile, which keeps setup fast during the session.
4. Copy the repo URL.

Using one repo for every step keeps the flow consistent:

- Render deploys from your repo.
- Your local clone uses your repo.
- Your AI coding tool edits your repo.
- Your pushed changes redeploy on Render.

> [!IMPORTANT]
> **Fallback only.** If you can't create a GitHub repo during the workshop, you can point Render at the public `render-examples/sf-pulse-python-workshop` repo for the initial deploy. You won't be able to push your Events feature to that repo or redeploy your changes from it later, so use this only if creating your own repo is blocked.

> [!NOTE]
> **Result:** You have a public GitHub repo URL for Render services, local development, and later pushes.

### 2. Join the shared Render workspace

Use the shared workspace for the hosted baseline app. The shared workspace gives you workshop infrastructure without requiring you to add payment details or manage credits during the session.

1. Sign up for Render.
2. Submit your email through the workspace invite form.
3. Accept the invite to the `AI Council` workspace.
4. In the Render Dashboard, switch to the `AI Council` workspace.

> [!NOTE]
> **Result:** You can create services in the `AI Council` workspace.

### 3. Deploy the Blueprint

Deploy the Blueprint to create your Render project plus the hosted SF Pulse stack: web service, cron job, Render Postgres database, and Key Value instance. The workflow service comes in step 4 (Render Workflows isn't first-class in Blueprint YAML yet).

First, personalize the project name so your services are easy to find in the shared workspace.

1. In your local clone of the repo, open `render.yaml`.
2. On line 2, change `name: sf-pulse-python` to `name: sf-pulse-<firstname-lastname>`.
3. Commit and push the change to `main`.

Now deploy it:

1. Open the Blueprint deploy flow for your public workshop repo.
2. Confirm `RENDER_API_KEY` is a real Render API key. Create one under **Account Settings > API Keys** if you don't have one yet.
3. Leave `SF_PULSE_WORKFLOW_SLUG` blank. You'll set it in step 5 once the workflow service exists.
4. Click **Deploy Blueprint**.

> [!NOTE]
> **Result:** You have a project named `sf-pulse-<firstname-lastname>` containing the web service, cron job, database, and Key Value instance. The cron job won't run successfully until you finish step 5.

### 4. Create the workflow service

Create the workflow service inside the project the Blueprint just made. This service runs the durable task code in `workflow/main.py`. The cron job calls it later to start `daily-refresh`.

1. In the Render Dashboard, open your `sf-pulse-<firstname-lastname>` project.
2. From inside the project, click **New > Workflow**. Starting from inside the project pre-selects it for the new service.
3. Choose **Public Git Repository**.
4. Use your public workshop repo URL.
5. Set the branch to `main`.
6. Set the name to `sf-pulse-workflow-<firstname-lastname>`.
7. Confirm the **Project** field is set to `sf-pulse-<firstname-lastname>` and the environment matches your Blueprint's environment. If it isn't, fix it now. You don't want your workflow service in a different project.
8. Set the build command to `pip install --upgrade uv && uv sync --frozen`.
9. Set the start command to `uv run python -m workflow.main`.
10. Attach the `sf-pulse-env` env group. This is a shared env group pre-created in the `AI Council` workspace for the workshop. It holds the OpenAI API key (`LLM_API_KEY`) and other LLM settings so you don't need to bring your own key.
11. Add `DATABASE_URL` as an env var on the service. Copy the value from the Internal Database URL of your Postgres database. Render Workflows doesn't yet support `fromDatabase` references in `render.yaml`, so you set this directly.
12. Click **Deploy workflow**.
13. After the service is live, open **Settings** and copy the workflow slug.

> [!NOTE]
> **Result:** You have a live workflow service inside your project, plus its slug ready to wire to the cron job.

### 5. Wire the cron job to the workflow

The cron job needs the workflow slug to know which task to trigger.

1. In your project, open the `sf-pulse-python-daily` cron service.
2. Add `SF_PULSE_WORKFLOW_SLUG` as an env var, set to the slug you copied in step 4.
3. Save. The cron service redeploys automatically.

> [!NOTE]
> **Result:** The cron job can now trigger `daily-refresh` on your workflow service.

### 6. Verify the hosted baseline

Confirm the initial app works before you start the local exercise. Verifying the known-good version first helps you tell the difference between setup issues and later implementation issues.

1. Open the web service URL.
2. Trigger the cron job manually from the Render Dashboard.
3. Open the workflow service logs.
4. Confirm that `daily-refresh` runs and restaurant data appears in the web app.

> [!NOTE]
> **Result:** The hosted app renders, `daily-refresh` runs, and restaurant data appears in the web app.

### 7. Switch to local development

Move to your local machine. This is where your AI coding tool edits the app and workflow code. The Render skills help your tool understand the deployed services, but the first validation happens locally.

```sh
brew install render
render skills install
render skills list
```

Clone your public workshop repo:

```sh
git clone <your-workshop-repo-url>
cd sf-pulse-python-workshop-<firstname-lastname>
uv sync
```

Configure local Postgres, then run migrations:

```sh
cp .env.example .env.local
uv run python -m bin.migrate
```

Set `DATABASE_URL` in `.env.local` before running migrations.

> [!NOTE]
> **Result:** You have the repo cloned, dependencies installed, the local environment configured, and database migrations applied.

### 8. Ask your coding agent to add events (local only)

Use your AI coding tool to change SF Pulse from a restaurant-only discovery workflow into a restaurant-and-events discovery workflow. This step is local-only. You'll deploy the changes in step 12.

`demo_prompt.md` is the implementation spec. It tells the agent to add the Events UI, storage, API routes, source fetchers, and workflow tasks. The verification steps inside it all target your local machine.

Apply this prompt to your AI coding tool:

```text
Follow the instructions in demo_prompt.md to add an Events feature to SF Pulse.

Scope:
- Local development only. Do not push, deploy, or touch any Render services.
- After editing the code, run the verification steps at the end of demo_prompt.md.
- Then help me run the workflow locally with `render workflows dev` and trigger
  the `daily-refresh` task so I can see events in my local database.
```

> [!NOTE]
> **Result:** Your local code includes an Events feature and new workflow tasks, but nothing has been deployed yet.

### 9. Understand the new workflow tasks

Before you run the workflow, identify the units of work the agent added. Each source task is independently retryable, and `daily-refresh` coordinates them.

The local code change should extend the workflow with these tasks:

| Task | Purpose |
| --- | --- |
| `fetch-funcheap` | Fetch structured SF events from Funcheap. |
| `fetch-famsf` | Fetch events from Fine Arts Museums of San Francisco. |
| `fetch-cal-academy` | Fetch events from California Academy of Sciences. |
| `search-events` | Search for event-related articles and pass them to extraction. |
| `daily-refresh` | Run restaurant and event sources in parallel, normalize results, deduplicate them, and call the persistence task. |
| `apply-discovered-items` | Write new restaurants and events to Postgres and broadcast realtime updates. |

The important pattern is fan-out and fan-in. Each source is isolated and retryable. The orchestrator tolerates failures from individual sources, then applies the candidates that succeeded.

> [!NOTE]
> **Result:** You can explain which tasks fetch event data, which task orchestrates the run, and which task writes results to Postgres.

### 10. Run the workflow locally

Start the local Render Workflows task server. This step verifies task registration, task execution, subtask fan-out, logs, and results without deploying. You should see the durable workflow model directly.

```sh
render workflows dev -- uv run python -m workflow.main
```

In another terminal, list registered local tasks:

```sh
render workflows tasks list --local
```

Run `daily-refresh` with this input:

```json
[]
```

Watch the logs. You should see the workflow fetch restaurant sources, fetch event sources, optionally run LLM extraction, deduplicate candidates, and call `apply-discovered-items`.

> [!NOTE]
> **Result:** A local `daily-refresh` run fetches restaurants and events, deduplicates candidates, and writes records to your local Postgres database.

### 11. Check the local app

Start the FastAPI app. The workflow proves the backend pipeline works. The local web app proves the new event data is visible to users.

```sh
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. The home page should include Restaurants and Events tabs. The Events tab should show events inserted by your local workflow run.

> [!NOTE]
> **Result:** The local home page includes Restaurants and Events tabs, and the Events tab shows data from your local workflow run.

### 12. Push and redeploy

Deploy only after your local workflow run succeeds. Now that the workflow works locally, push your changes so Render can run the same code in the hosted environment.

You can do this by hand:

```sh
git add .
git commit -m "Add Events feature"
git push
```

Then trigger the cron job from the Render Dashboard and watch the workflow logs.

Or hand the deploy phase to your AI coding tool with this prompt:

```text
The Events feature works locally. Now deploy it to my Render workspace.

Use the Render skills you have installed:
- Commit and push the current changes on this branch.
- Watch the deploy logs for both the web service and the workflow service.
- Once both services are live, trigger the `daily-refresh` cron job manually
  in the Render Dashboard (or via the Render CLI).
- Tail the workflow service logs and confirm `daily-refresh` completes.
- Open the hosted web app URL and confirm the Events tab shows events.

If any deploy fails, use the Render skills to read the logs and propose a fix
before retrying.
```

> [!NOTE]
> **Result:** Your GitHub repo contains the Events feature, and your hosted Render app redeploys from that repo.

## Troubleshooting

- `Task not found`: Restart `render workflows dev` and run `render workflows tasks list --local`.
- No events appear locally: Confirm `DATABASE_URL` points to the database where you ran migrations.
- Source fetches fail: Check the local workflow logs. The orchestrator should continue if another source succeeds.
- LLM extraction is skipped: Set `LLM_API_KEY` for full extraction. Without it, only non-LLM event sources produce event records.
- The deployed cron job fails with `RENDER_API_KEY` missing: Set a real Render API key on the cron job. Don't use the workflow slug as the API key.

## Reference

### Stack

- Python 3.12+
- [FastAPI](https://fastapi.tiangolo.com/) and [Uvicorn](https://www.uvicorn.org/)
- [asyncpg](https://magicstack.github.io/asyncpg/) for raw SQL (no ORM)
- [Pydantic v2](https://docs.pydantic.dev/) for request and response validation
- [httpx](https://www.python-httpx.org/) and [selectolax](https://github.com/rushter/selectolax) for scraping
- [OpenAI](https://github.com/openai/openai-python) and [Anthropic](https://github.com/anthropics/anthropic-sdk-python) Python SDKs for provider-agnostic LLM extraction
- [Render Python SDK](https://github.com/render-oss/sdk/tree/main/python) for Render Workflows
- [pywebpush](https://github.com/web-push-libs/pywebpush) for web push
- [redis-py](https://redis.readthedocs.io/) async and [sse-starlette](https://github.com/sysid/sse-starlette) for realtime
- React and Vite for the workflow diagram
- `uv` for package management

### Repo layout

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
migrations/              # plain SQL (0001-0011)
static/
  diagram/               # Vite build output (gitignored, built during deploy)
  styles/, icons/, home.js, map.js, service-worker.js, manifest.webmanifest
web/diagram/             # Vite + React sub-project for the workflow diagram
tests/                   # pytest suite (testcontainers Postgres)
docs/                    # architecture, workflow setup, deployment
render.yaml              # Render Blueprint
```

### Environment variables

| Variable | Where used | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | web, cron, workflow | PostgreSQL connection string. |
| `REDIS_URL` | web | Redis® pub/sub for multi-instance SSE (optional). |
| `CRON_SECRET` | web | Required header on protected mutation endpoints. |
| `APP_URL` / `RENDER_EXTERNAL_URL` | web | Public URL used in RSS feed and push payloads. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | web, workflow | Web push (optional). |
| `LLM_API_KEY` | workflow | OpenAI or Anthropic key. Without it, only regex sources produce results. |
| `LLM_PROVIDER` | workflow | `openai` or `anthropic`. Auto-detected if blank. |
| `LLM_MODEL` | workflow | Model override. |
| `RENDER_API_KEY` | cron | Used by `bin/trigger_workflow.py` to start the daily workflow. |
| `SF_PULSE_WORKFLOW_SLUG` | cron | Slug of the workflow service in Render. |

### Tests

```sh
uv run pytest -q
```

Tests use [testcontainers-python](https://testcontainers-python.readthedocs.io/), which spins up a real PostgreSQL container per session, so **Docker must be running**. Pure-utility tests (dates, html, identity, and so on) run without Docker.

### Documentation

- [docs/architecture.md](docs/architecture.md): system overview and data flow.
- [docs/deployment.md](docs/deployment.md): full deploy walkthrough.
- [docs/openai-api-permissions.md](docs/openai-api-permissions.md): required OpenAI key permissions.

## License

MIT

---

Redis is a registered trademark of Redis Ltd. Any rights therein are reserved to Redis Ltd. Any use by Render Inc is for referential purposes only and does not indicate any sponsorship, endorsement or affiliation between Redis and Render Inc.
