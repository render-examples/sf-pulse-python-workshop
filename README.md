# SF Pulse Workshop Companion Repo

This is the companion repo for the **Should Agents Be Durable?** workshop hosted at AI Council. It's a GitHub template. Click **Use this template** above to create your own copy, then follow the steps below.

By the end of the workshop, you'll have shipped a durable agent: not a one-off prompt, but a repeatable Render Workflows pipeline that you ran locally, extended with new tasks, and redeployed.

## What you'll build

You'll work with SF Pulse, a FastAPI app whose agent behavior is a durable Render Workflows pipeline. Today the pipeline runs a daily refresh task that discovers new SF restaurant openings, normalizes candidates, deduplicates them, and writes the results to Render Postgres.

The workshop arc has two halves:

1. **Deploy the starter app** to the shared `AI Council` Render workspace and verify it works, so you can see the production shape of the app before you change any code.
2. **Extend the pipeline** locally with an Events feature, validate it against your local Postgres, then push and let your hosted services pick up the change.

Adding an Events feature is the concrete exercise: new source tasks, a broader orchestrator, the same deduplication and persistence path. By the end, `daily-refresh` should fan out across both restaurant and event sources, and the web app should show an Events tab backed by data from your database.

### Architecture

```mermaid
flowchart LR
    user([Browser])

    subgraph project["Your Render project"]
        direction TB
        web["Web service<br/>FastAPI + SSE"]
        cron["Cron job<br/>daily trigger"]
        wf["Workflow service<br/>daily-refresh"]
        db[("Render Postgres")]
        kv[("Render Key Value")]
    end

    sources(["Source sites<br/>Eater, SFist, Funcheap, ..."])
    llm(["LLM API<br/>OpenAI / Anthropic"])

    user -->|HTTP + SSE| web
    web --> db
    web <--> kv

    cron -->|trigger| wf
    wf -->|scrape| sources
    wf -->|extract| llm
    wf -->|upsert| db
    wf -->|publish update| kv
```

The cron job triggers `daily-refresh` on the workflow service. The workflow fans out across source tasks (scraping and LLM extraction), deduplicates the results, upserts them into Postgres, and publishes a realtime update to Key Value. The web service reads from Postgres for page loads and subscribes to Key Value for SSE so the UI updates without a refresh.

The workshop has you extend this pipeline with new source tasks for SF events.

For a deeper walkthrough of why each component exists (why a workflow service, why Key Value, why Postgres) and a sequence diagram of the daily-refresh flow, see [docs/architecture.md](docs/architecture.md).

## What you'll learn

- How to split an agent workflow into retryable tasks
- How to fan out across multiple sources and fan in normalized results
- How to treat an LLM as one stage in a durable pipeline, not the whole system
- How to use Postgres as the source of truth for discovered data
- How to run and inspect workflow tasks locally before deploying

## Workshop steps

### 1. Create your workshop repo

Create your own public GitHub repo from this template. Use this repo for the rest of the workshop so Render and your local machine point at the same codebase.

1. Click the green **Use this template** button in the top right of this repo, then choose **Create a new repository**.
2. Name the repo `sf-pulse-python-workshop-<firstname-lastname>`.
3. Set the repo visibility to Public. A public repo lets you add it to the workshop Render workspace without connecting your GitHub profile, which keeps setup fast during the session.
4. Copy the repo URL.

Using one repo for every step keeps the flow consistent:

- Render deploys from your repo.
- Your local clone uses your repo.
- Your AI coding tool edits your repo.
- Your pushed changes redeploy on Render.

> [!TIP]
> You now have a public GitHub repo URL ready for Render services, local development, and later pushes.

### 2. Join the shared Render workspace

Use the shared workspace for the hosted starter app. The shared workspace gives you workshop infrastructure without requiring you to add payment details or manage credits during the session.

1. If you don't have a Render account yet, [sign up for Render](https://dashboard.render.com/register). If you already have one, just [log in](https://dashboard.render.com/login).
2. Submit the email address tied to your Render account through the [workshop workspace invite form](https://docs.google.com/forms/d/e/1FAIpQLSec77W4u00ZkENLOVzXSqPWvQ5lPQMCHCFLa4JOHn30l-Ad8Q/viewform). The email address must match your Render account so the invite reaches the right user.
3. Check your inbox for the `AI Council` workspace invite from Render and accept it.
4. In the Render Dashboard, accept the invite and switch to the `AI Council` workspace.

![Switching to the AI Council workspace in the Render Dashboard sidebar](docs/images/workspace-switcher.png)

> [!TIP]
> You can now create services in the `AI Council` workspace.

### 3. Deploy the Blueprint

Deploy the Blueprint to create your Render project plus the hosted SF Pulse stack: web service, cron job, Render Postgres database, and Key Value instance. The workflow service comes in step 4 (Render Workflows isn't first-class in Blueprint YAML yet).

First, personalize the project name so your services are easy to find in the shared workspace.

1. In your local clone of the repo, open `render.yaml`.
2. On line 2, change `name: sf-pulse-python` to `name: sf-pulse-<firstname-lastname>`.
3. Commit and push the change to `main`.

Now deploy it:

1. Open the Blueprint deploy flow for your public workshop repo.
2. Open the **Advanced** tab and confirm the `sf-pulse-env` env group from the `AI Council` workspace is attached. This group provides `RENDER_API_KEY`, `LLM_API_KEY`, and the other shared secrets, so you don't need to bring your own.
3. Leave `SF_PULSE_WORKFLOW_SLUG` blank. You'll set it in step 5 once the workflow service exists.
4. Click **Deploy Blueprint**.

![Blueprint deploy form with the Advanced tab expanded showing the sf-pulse-env env group attachment](docs/images/blueprint-deploy-advanced.png)

> [!IMPORTANT]
> **The cost estimate at the bottom is informational only.** The `AI Council` workspace is the workshop's shared workspace, so you won't be charged. The workspace is torn down after the conference.

> [!TIP]
> You now have a project named `sf-pulse-<firstname-lastname>` containing the web service, cron job, database, and Key Value instance. The cron job won't run successfully until you finish step 5.

### 4. Create the workflow service

Create the workflow service inside the project the Blueprint just made. This service runs the durable task code in `workflow/main.py`. The cron job calls it later to start `daily-refresh`.

1. In the Render Dashboard, open your `sf-pulse-<firstname-lastname>` project.
2. From inside the project, click **New > Workflow**. Starting from inside the project pre-selects it for the new service.

   ![Clicking New > Workflow from inside the personalized project](docs/images/new-workflow-from-project.png)

3. Choose **Public Git Repository**.
4. Use your public workshop repo URL.
5. Set the branch to `main`.
6. Set the name to `sf-pulse-workflow-<firstname-lastname>`.
7. Confirm the **Project** field is set to `sf-pulse-<firstname-lastname>` and the environment matches your Blueprint's environment. If it isn't, fix it now. You don't want your workflow service in a different project.

   ![Workflow creation form with the Project field highlighted showing the personalized project](docs/images/workflow-project-field.png)

8. Set the build command to `pip install --upgrade uv && uv sync --frozen`.
9. Set the start command to `uv run python -m workflow.main`.
10. Attach the `sf-pulse-env` env group. This is a shared env group pre-created in the `AI Council` workspace for the workshop. It holds the OpenAI API key (`LLM_API_KEY`) and other LLM settings so you don't need to bring your own key.
11. Add `DATABASE_URL` as an env var on the service. Copy the value from the Internal Database URL of your Postgres database. Render Workflows doesn't yet support `fromDatabase` references in `render.yaml`, so you set this directly.
12. Click **Deploy workflow**.
13. After the service is live, open **Settings** and copy the workflow slug.

    ![Workflow service Settings tab with the slug highlighted](docs/images/workflow-slug-settings.png)

> [!TIP]
> You now have a live workflow service inside your project, plus its slug ready to wire to the cron job.

### 5. Wire the cron job to the workflow

The cron job needs the workflow slug to know which task to trigger.

1. In your project, open the `sf-pulse-python-daily` cron service.
2. Add `SF_PULSE_WORKFLOW_SLUG` as an env var, set to the slug you copied in step 4.
3. Save. The cron service redeploys automatically.

![Cron service Environment tab with SF_PULSE_WORKFLOW_SLUG being added](docs/images/cron-env-var.png)

> [!TIP]
> Your cron job can now trigger `daily-refresh` on your workflow service.

### 6. Verify the hosted starter app

Confirm the initial app works before you start the local exercise. Verifying the known-good version first helps you tell the difference between setup issues and later implementation issues.

1. In your `sf-pulse-<firstname-lastname>` project, open the `sf-pulse-python` web service. Its URL is at the top of the service page and looks like `https://sf-pulse-python-<hash>.onrender.com`. Open it in a new tab to see the SF Pulse home page.

   ![Web service page with the public onrender.com URL highlighted at the top](docs/images/web-service-url.png)

2. Back in the Dashboard, open the `sf-pulse-python-daily` cron job and click **Trigger Run**.
3. Open the workflow service and watch the **Logs** tab. `daily-refresh` should fan out across the source tasks, run extraction, and call `apply-discovered-items`.

   ![Workflow service Logs tab during a daily-refresh run](docs/images/workflow-logs.png)

4. Refresh the web service URL. Restaurant cards should appear on the home page.

> [!TIP]
> Your hosted starter app is running. `daily-refresh` completed successfully and restaurant data appears in the web app.

### 7. Switch to local development

Switch from the Render Dashboard to your terminal and editor. This is where your AI coding tool edits the app and workflow code. The Render skills help your tool understand the deployed services, but the first validation happens locally.

Install the Render CLI and skills (used in step 10 to run the workflow runtime locally):

```sh
brew install render
render skills install
render skills list
```

> [!TIP]
> Wire your AI coding tool to Render so the agent can list services, query your database, and read logs directly during steps 8–12. Without it, the agent flies blind when something on Render misbehaves (like the workflow writing to the wrong database).
>
> - **Cursor users**: install the [Render plugin for Cursor](https://cursor.com/marketplace/render). It bundles the Render skills, MCP config, hooks, and rules in one step.
> - **Any other AI tool** (Codex, Claude Code, Windsurf, Claude Desktop, VS Code, ...): set up the [Render MCP server](https://render.com/docs/mcp-server). The page has copy-paste config for each tool.

Clone your public workshop repo:

```sh
git clone <your-workshop-repo-url>
cd sf-pulse-python-workshop-<firstname-lastname>
```

Now pick one of the two local setups below.

#### Option A: Docker Compose (recommended)

If you have Docker Desktop, this is the fastest path. One command brings up Postgres, Valkey (Render Key Value's engine), and the FastAPI app with migrations applied.

```sh
docker compose up --build
```

Once the logs settle, the app is accessible at:

- **App UI:** <http://localhost:8000>
- **Postgres:** `localhost:5432` (user `sfpulse`, password `sfpulse`, database `sfpulse`)
- **Valkey:** `localhost:6379`

Postgres and Valkey are exposed on the host so `render workflows dev` in step 10 can connect to them from outside the compose network.

For step 10, set `DATABASE_URL` and `REDIS_URL` in `.env.local` so the host-side workflow runtime can reach the dockerized services:

```sh
cp .env.example .env.local
# Edit .env.local and set:
# DATABASE_URL=postgresql://sfpulse:sfpulse@localhost:5432/sfpulse
# REDIS_URL=redis://localhost:6379
```

#### Option B: Native uv (no Docker)

If you'd rather run everything on your host:

```sh
uv sync
cp .env.example .env.local
# Set DATABASE_URL in .env.local to point at your local Postgres
uv run python -m bin.migrate
```

You'll need PostgreSQL 16 installed locally (`brew install postgresql@16` on macOS). Valkey or Redis is optional; without it, SSE falls back to in-process.

> [!TIP]
> You now have the repo cloned, dependencies installed, the local environment configured, and database migrations applied.

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

> [!TIP]
> Your local code now includes an Events feature and new workflow tasks. Nothing has been deployed yet.

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

> [!TIP]
> You can now explain which tasks fetch event data, which task orchestrates the run, and which task writes results to Postgres.

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

> [!TIP]
> Your local `daily-refresh` run fetched restaurants and events, deduplicated candidates, and wrote records to your local Postgres database.

### 11. Check the local app

The workflow proves the backend pipeline works. The local web app proves the new event data is visible to users.

If you're using Docker Compose, the app is already running at <http://localhost:8000> with hot reload — your agent's edits are picked up automatically.

If you're using the native uv setup, start the FastAPI app:

```sh
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. The home page should include Restaurants and Events tabs. The Events tab should show events inserted by your local workflow run.

> [!TIP]
> Your local home page now shows Restaurants and Events tabs, with the Events tab populated by your local workflow run.

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

> [!TIP]
> Your GitHub repo now contains the Events feature, and your hosted Render app has redeployed with it.

## Troubleshooting

- `Task not found`: Restart `render workflows dev` and run `render workflows tasks list --local`.
- No events appear locally: Confirm `DATABASE_URL` points to the database where you ran migrations.
- Source fetches fail: Check the local workflow logs. The orchestrator should continue if another source succeeds.
- LLM extraction is skipped: Set `LLM_API_KEY` for full extraction. Without it, only non-LLM event sources produce event records.
- The deployed cron job fails with `RENDER_API_KEY` missing: Set a real Render API key on the cron job. Don't use the workflow slug as the API key.
- `docker compose up` exits with a port already in use: another process is bound to `5432`, `6379`, or `8000`. Stop the conflicting service or edit `compose.yaml` to map a different host port.
- `render workflows dev` can't reach Postgres while compose is up: confirm `DATABASE_URL` in `.env.local` points at `postgresql://sfpulse:sfpulse@localhost:5432/sfpulse`, not `db:5432` (`db` only resolves inside the compose network).

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
compose.yaml             # Local Docker Compose: Postgres + Valkey + API
Dockerfile               # Container build for the API
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
