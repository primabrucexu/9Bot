# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

- Linux dev startup: `./start.sh`
- Windows dev startup: `start.bat`
- Both startup scripts create `.venv` if needed, install `requirements.txt`, and run `uvicorn app.main:app --reload`.
- For test work, install dev dependencies manually:
  - Linux: `.venv/bin/python -m pip install -r requirements-dev.txt`
  - Windows: `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
- Run all tests:
  - Linux: `.venv/bin/python -m pytest`
  - Windows: `.venv\Scripts\python.exe -m pytest`
- Run one test file:
  - Linux: `.venv/bin/python -m pytest tests/test_indicators.py`
  - Windows: `.venv\Scripts\python.exe -m pytest tests/test_indicators.py`
- Run a single test by name filter:
  - Linux: `.venv/bin/python -m pytest tests/test_indicators.py -k summary_and_chart_payload_are_usable`
  - Windows: `.venv\Scripts\python.exe -m pytest tests/test_indicators.py -k summary_and_chart_payload_are_usable`
- No dedicated lint or build command is configured in the repository today.

## Architecture overview

- `app/main.py` is the FastAPI entrypoint. It initializes SQLite during the app lifespan, mounts `/static`, stores `settings` and `templates` on `app.state`, and registers the page router plus the JSON API router.
- `app/config.py` centralizes configuration in a cached `Settings` dataclass loaded from `.env`. Defaults are documented in `.env.example`. The local database defaults to `data/9bot.db`.
- `app/db.py` is the persistence layer. It uses raw `sqlite3` plus pandas reads/writes rather than an ORM. The app persists three concepts only: watchlist items, cached daily bars, and generated daily reports.

## Request flow and responsibilities

- `app/routers/pages.py` serves the server-rendered HTML pages: dashboard, stock detail, latest report, and report-by-date.
- `app/routers/api.py` exposes the JSON endpoints for watchlist changes, market refresh, chart payloads, and report generation.
- Routers are intentionally thin. Business logic belongs in `app/services`, and persistence belongs in `app/db.py`.

## Service layer

- `app/services/market_data.py` handles A-share symbol validation, AkShare lookups, refreshes of local historical data, and dashboard row assembly.
- `app/services/indicators.py` computes MA5/10/20/60, MACD, RSI14, rule-based signal summaries, and the chart payload used by the detail page.
- `app/services/report_generator.py` builds a compact report context from the locally cached bars, calls Anthropic, and saves the generated markdown back into SQLite.
- `app/services/prompt_builder.py` contains the fixed Chinese system prompt and the deterministic user-message builder for report generation.

## Data flow

1. Watchlist changes are stored in SQLite.
2. Refresh pulls snapshot/history data from AkShare and upserts normalized bars into `daily_bars`.
3. Dashboard and stock-detail views read from the local cache and compute indicators on demand.
4. AI report generation uses the same cached local data instead of calling AkShare again during report creation.

## Frontend structure

- The UI is mostly server-rendered Jinja templates in `app/templates` with lightweight progressive enhancement from `app/static`.
- There is no frontend build pipeline.
- `app/static/dashboard.js` drives add/remove/refresh/report actions via fetch calls to `/api/...` and then reloads or redirects.
- `app/static/stock_detail.js` fetches `/api/stocks/{symbol}/chart` and renders K-line, volume, MACD, and RSI charts client-side.
- ECharts is loaded directly from CDN by the stock detail template, so chart changes usually involve both the template and `stock_detail.js`.

## Anthropic integration

- The project uses the official Python `anthropic` SDK.
- The default model is `claude-opus-4-6`.
- Report generation uses streaming, adaptive thinking, and `output_config={"effort": "high"}`.
- Prompt stability matters: `prompt_builder.py` serializes report context with `sort_keys=True`, and `report_generator.py` marks the system prompt as ephemeral cacheable content. Preserve that deterministic structure when changing the report prompt path.

## Testing notes

- `tests/conftest.py` provides a `Settings` factory and sample bar fixture so tests do not depend on the real local database layout.
- `tests/test_report_generation.py` mocks Anthropic calls; report tests should stay offline.
- There are currently no tests for live AkShare integration, so changes in `market_data.py` should be validated carefully if they touch upstream column mappings or refresh behavior.
