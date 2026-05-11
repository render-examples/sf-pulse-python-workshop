# Deployment

This walks through deploying SF Pulse Python to Render from scratch.

## What `render.yaml` provisions

- `sf-pulse-python` — web service (FastAPI)
- `sf-pulse-python-daily` — cron service (triggers the workflow)
- `sf-pulse-python-db` — PostgreSQL
- `sf-pulse-python-realtime` — Redis (key-value)

What it does **not** provision:

- `sf-pulse-python-workflow` — the workflow service is created manually (see the workshop steps in the [README](../README.md#4-create-the-workflow-service))

## Step-by-step

### 1. Fork or clone the repo

Push a copy of `render-examples/sf-pulse-python-workshop` to your own GitHub account if you want to make customizations. Otherwise the `Deploy to Render` button works directly against `render-examples/sf-pulse-python-workshop`.

### 2. Create the env group

Dashboard → **Env Groups** → **New Env Group**: `sf-pulse-python-env`

Required:

- `LLM_API_KEY` — OpenAI or Anthropic key (without it, only regex sources work)

Optional:

- `LLM_PROVIDER`, `LLM_MODEL` — overrides
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` — required only for push notifications. Generate with `uv run python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); v.save_key('private.pem'); v.save_public_key('public.pem')"` (or any standard VAPID generator).
- `APP_URL` — public URL used in RSS / push payloads. Render auto-sets `RENDER_EXTERNAL_URL` so this is usually unnecessary.

### 3. Deploy the Blueprint

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Frender-examples%2Fsf-pulse-python-workshop)

Or `New` → `Blueprint` → connect the repo. Render reads `render.yaml` and creates the four services.

### 4. Wire up the database & redis URLs

After the first deploy, set on the env group:

- `DATABASE_URL` — copy from `sf-pulse-python-db` Internal Database URL
- `REDIS_URL` — copy from `sf-pulse-python-realtime` Internal Connection URL

(`render.yaml` already wires these on the web service via `fromDatabase`/`fromService`, but the env group is shared with cron and workflow services that need the same URLs.)

### 5. Create the workflow service

Follow steps 4 and 5 in the [workshop guide](../README.md#4-create-the-workflow-service). Then set `RENDER_API_KEY` and `SF_PULSE_WORKFLOW_SLUG` on the cron service.

### 6. First data load

Either wait for the daily 7:00 AM PDT cron, or **Trigger Run** the cron service in the Dashboard.

### 7. Verify

- `https://sf-pulse-python.onrender.com/api/healthz` returns `{"ok": true}`
- The home page loads and shows the diagram tab
- Workflow logs show all source tasks completing
- Restaurants appear after the first successful run

## Build details

- **Web service buildCommand**:
  ```sh
  cd web/diagram && npm ci && npm run build && cd ../..
  pip install --upgrade uv && uv sync --frozen
  ```
  This builds the React diagram into `static/diagram/` and installs Python deps.
- **Pre-deploy**: `uv run python -m bin.migrate` runs migrations against the production DB.
- **Start**: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Common deploy errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `DATABASE_URL is required` | env group missing the URL | Set it from the Postgres internal URL |
| `Module not found: workflow.main` | Workflow service can't find the package | Verify build command ran `uv sync --frozen` |
| `405 Method Not Allowed` on `/api/push/subscribe` | Probably hitting GET; should be POST | Check curl/client method |
| Diagram tab empty | `static/diagram/` wasn't built | Verify the web service build log includes `npm run build` |
| Push fanout silently skipped | VAPID keys not set | Set `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` on the env group |
