# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Development commands

### Full-stack dev startup

- Linux dev startup: `./start.sh`
- Windows dev startup: `start.bat`
- Both startup scripts live at the repository root, create `backend/.venv` if needed, install `backend/requirements.txt`, install frontend dependencies from `frontend`, and start:
  - FastAPI backend on `127.0.0.1:8000`
  - Vite frontend on `127.0.0.1:5173`

### Backend test work

- Install dev dependencies manually:
  - Linux: `cd backend && .venv/bin/python -m pip install -r requirements-dev.txt`
  - Windows: `cd backend && .venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
- Run all backend tests:
  - Linux: `cd backend && .venv/bin/python -m pytest`
  - Windows: `cd backend && .venv\Scripts\python.exe -m pytest`
- Run one backend test file:
  - Linux: `cd backend && .venv/bin/python -m pytest tests/test_indicators.py`
  - Windows: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_indicators.py`
- Run a single backend test by name filter:
  - Linux: `cd backend && .venv/bin/python -m pytest tests/test_indicators.py -k summary_and_chart_payload_are_usable`
  - Windows: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_indicators.py -k summary_and_chart_payload_are_usable`

### Frontend work

- Frontend lives in `frontend/`
- Common commands:
  - `cd frontend && npm install`
  - `cd frontend && npm run dev`
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint`

## Architecture overview

### Backend

- `backend/app/main.py` is the FastAPI entrypoint. It initializes SQLite during the app lifespan, stores `settings` on `app.state`, applies CORS, and registers the JSON API router.
- `backend/app/config.py` centralizes configuration in a cached `Settings` dataclass loaded from `backend/.env`. Defaults are documented in `backend/.env.example`. The local backend database defaults to `backend/data/9bot.db`.
- `backend/app/db.py` is the persistence layer. It uses raw `sqlite3` plus pandas reads/writes rather than an ORM. The app persists three concepts only: watchlist items, cached daily bars, and generated daily reports.

### Request flow and responsibilities

- `backend/app/routers/api.py` exposes the JSON endpoints for dashboard reads, watchlist changes, market refresh, chart payloads, and report generation.
- Routers are intentionally thin. Business logic belongs in `backend/app/services`, and persistence belongs in `backend/app/db.py`.

### Service layer

- `backend/app/services/market_data.py` handles A-share symbol validation, AkShare lookups, refreshes of local historical data, and dashboard row assembly.
- `backend/app/services/indicators.py` computes MA5/10/20/60, MACD, RSI14, rule-based signal summaries, and the chart payload used by the frontend stock detail page.
- `backend/app/services/report_generator.py` builds a compact report context from the locally cached bars, calls Anthropic, and saves the generated markdown back into SQLite.
- `backend/app/services/prompt_builder.py` contains the fixed Chinese system prompt and the deterministic user-message builder for report generation.

### Frontend

- Frontend code lives in `frontend/src`.
- `frontend/src/App.tsx` defines the React Router routes for dashboard, stock detail, and report pages.
- `frontend/src/pages/DashboardPage.tsx` drives add/remove/refresh/report actions via API calls.
- `frontend/src/pages/StockDetailPage.tsx` fetches `/api/stocks/{symbol}` and `/api/stocks/{symbol}/chart`, then renders K-line, volume, MACD, and RSI charts with ECharts.
- `frontend/src/pages/ReportPage.tsx` loads latest or date-specific reports from the backend API.
- `frontend/src/api/client.ts` provides the shared fetch wrapper and `frontend/src/api/types.ts` holds response types.

## Data flow

1. Watchlist changes are stored in SQLite.
2. Refresh pulls snapshot/history data from AkShare and upserts normalized bars into `daily_bars`.
3. Dashboard and stock-detail APIs read from the local cache and compute indicators on demand.
4. Frontend renders dashboard, stock detail, and report screens from API responses.
5. AI report generation uses the same cached local data instead of calling AkShare again during report creation.

## Anthropic integration

- The project uses the official Python `anthropic` SDK.
- The default model is `claude-opus-4-6`.
- Report generation uses streaming, adaptive thinking, and `output_config={"effort": "high"}`.
- Prompt stability matters: `backend/app/services/prompt_builder.py` serializes report context with `sort_keys=True`, and `backend/app/services/report_generator.py` marks the system prompt as ephemeral cacheable content. Preserve that deterministic structure when changing the report prompt path.

## Testing notes

- `backend/tests/conftest.py` provides a `Settings` factory and sample bar fixture so tests do not depend on the real local database layout.
- `backend/tests/test_report_generation.py` mocks Anthropic calls; report tests should stay offline.
- There are currently no tests for live AkShare integration, so changes in `backend/app/services/market_data.py` should be validated carefully if they touch upstream column mappings or refresh behavior.

## Restructure caveat

- `.env`, `.venv`, and `data/9bot.db` may still exist at the repository root from before the backend move. They are not tracked, so they do not move automatically with code changes.
- If local development breaks after the restructure, first check whether those files need to be recreated or moved under `backend/`.
