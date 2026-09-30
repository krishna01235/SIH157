# NIGRANI-SA · SOC Assessment Workbench

NIGRANI-SA turns a periodic SOC submission into traceable observations for a human supervisor. Upload asset, alert, and case CSVs; run three transparent checks; inspect the source records behind each observation; save a review decision; and export a review CSV. The local UI also includes a one-click synthetic example for quick evaluation.

The MVP covers three working features: **validated evidence import**, **explainable assessment**, and **supervisor review with export**. It does not assign a security grade or claim that an observation proves compromise. The full source problem statement available for planning was incomplete, so the broader requirements in the original reference document have not been treated as verified.

## Quick start with Docker

Docker Desktop or Docker Engine with Compose is required. From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Open <http://127.0.0.1:8000>. Wait for the `app` service to become healthy. The first build needs package-registry access; ordinary restarts use the local image. Data is stored in a named Docker volume and remains after `docker compose down` or image replacement. Do not use `docker compose down -v` unless you intend to delete that evidence and the saved reviews.

If port 8000 is already in use, set `HOST_PORT=18000` and `ALLOWED_ORIGINS=http://127.0.0.1:18000,http://localhost:18000` in `.env`, then open port 18000. The service still binds to loopback only. On POSIX, use `cp .env.example .env`; the remaining Docker commands are the same.

Choose **Explore sample assessment** to load two synthetic entities through the normal importer and rule engine. The signal example shows exact counts of **2/6** rapid closures, **1/5** cases with zero recorded investigations, and **1/4** in-scope critical assets with no alert in a declared complete export. [The evaluator guide](docs/demo-guide.md) walks through the full three-minute review.

## Source development

Tested locally with Python 3.13.3, Node 22, uv 0.12.21, and Docker 29.5.3. Python 3.12–3.13 is supported by the backend manifest. In one terminal from the repository root:

```powershell
uv sync --project backend --frozen
Set-Location backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to the local backend. Source development uses the ignored `backend/data/sat-sa.db`; the root `.env.example` is for Compose and is not needed for these commands. On POSIX, use `backend/.venv/bin/alembic`, `backend/.venv/bin/uvicorn`, and the same `npm` commands.

Run backend lint and tests with `cd backend && .venv/Scripts/ruff.exe check . && .venv/Scripts/pytest.exe -q` on Windows (use `.venv/bin/` on POSIX). Run `npm run typecheck`, `npm test`, and `npm run build` in `frontend`. The browser suite is `npm run test:e2e`; outside CI it expects backend port 8000 and Vite port 5173, or set `PLAYWRIGHT_BASE_URL` to the packaged app. Set `PLAYWRIGHT_CHANNEL=chrome` to use an installed Chrome instead of downloading Playwright Chromium.

The CSV contract and validation limits are in [data-contract.md](docs/data-contract.md). [Architecture](docs/architecture.md) explains the extension points. [Deployment and recovery](docs/deployment.md) covers offline image transfer, backup, restore, and updates. [Verification notes](docs/verification.md) record the measured capacity check and test coverage. The original [implementation plan](implementation-plan.md) describes the scoped decisions and milestone history.
