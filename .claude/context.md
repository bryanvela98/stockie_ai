# Stockie AI — Cold-Start Context

> **For Claude:** Read this file at the start of every conversation before taking any action.
> **Update rule:** After every completed sprint task, mark it ✅ here and update the "What has been built" table.
> Full backlog → `docs/PLANNING_tasks.md` | Feature plan → `docs/PLANNING_features.md`

---

## Active sprint: Sprint 2 — Ingestion pipeline + price storage (Weeks 5–6)

**Goal:** Scheduled jobs pull daily OHLCV and quarterly fundamentals into Postgres. Time-series queries are fast.

### Checklist

| # | Status | Owner | Task |
|---|--------|-------|------|
| 1 | ✅ | @bvela | Add Celery + Redis broker; one worker container in `docker-compose` |
| 2 | ✅ | @bvela | `daily_prices` Celery beat task: fetch + upsert OHLCV for all tracked tickers |
| 3 | ✅ | @bvela | `quarterly_fundamentals` Celery beat task: pull income/balance/cashflow + key ratios |
| 4 | ✅ | @bvela | Backfill script: load N years of history for the initial universe |
| 5 | ✅ | @bvela | Convert `price_bars` table to TimescaleDB hypertable; add compound index `(ticker_id, timestamp)` |
| 6 | ✅ | @bvela | `GET /tickers/{symbol}/prices?timeframe=1d&from=...&to=...` endpoint |
| 7 | ✅ | @bvela | Corporate-actions handling: store splits and dividends, expose adjusted-close |
| 8 | ✅ | @bvela | "As-of" timestamp threaded through every endpoint response |
| 9 | ✅ | @bvela | Tests: ingestion idempotency (re-run doesn't duplicate), split-adjustment correctness |
| 10 | ⬜ | @despinoza | Integrate TradingView Lightweight Charts on the ticker page |
| 11 | ⬜ | @despinoza | Timeframe toggle (1D/1W/1M/3M/1Y/5Y/Max) hitting the prices endpoint |
| 12 | ⬜ | @despinoza | "Data as of" badge component, used across the app |

---

## Completed sprint: Sprint 0 — Scaffolding (Weeks 1–2)

**Goal:** Full stack running locally. No business logic yet.

### Checklist

| # | Status | Owner | Task |
|---|--------|-------|------|
| 1 | ✅ | @bvela | Repo, CLAUDE.md, PLANNING docs, .gitignore, LICENSE |
| 2 | ✅ | @bvela | FastAPI + Pydantic Settings + `/health` endpoint + structlog |
| 3 | ✅ | @bvela | `docker-compose.yml` with TimescaleDB (pg16) + Redis |
| 4 | ✅ | @bvela | Alembic migrations configured + empty initial revision |
| 5 | ✅ | @bvela | Pre-commit (ruff + black + mypy) + pytest skeleton |
| 6 | ✅ | @despinoza | Next.js 14 + TypeScript + Tailwind initialized |
| 7 | ✅ | @despinoza | ESLint + Prettier + shadcn/ui component library |
| 8 | ✅ | @despinoza | Typed API client (`openapi-typescript`) |
| 9 | ✅ | @despinoza | Placeholder landing page calling `/health` |
| 10 | ✅ | @both | GitHub Actions CI — lint + tests on every PR |
| 11 | ✅ | @both | Issue/PR template + branch naming documented |
| 12 | ✅ | @both | End-to-end smoke test (`docker compose up` → frontend reads backend) |

---

## What has been built

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `app/core/config.py` | `AppSettings` (Pydantic BaseSettings); `get_settings()` singleton |
| `app/core/db.py` | Async engine, `AsyncSessionLocal`, `get_db()` FastAPI dependency |
| `app/core/logging.py` | `configure_logging()` — pretty in dev, JSON in prod (structlog) |
| `app/models/base.py` | `DeclarativeBase` — all future ORM models inherit from this |
| `app/api/v1/health.py` | `GET /health` → `{status, version, environment, timestamp}` |
| `app/main.py` | `create_app()` factory; lifespan hooks; router registration |
| `app/data_providers/__init__.py` | Barrel export: interfaces, value objects, exceptions |
| `app/data_providers/exceptions.py` | `ProviderError`, `TickerNotFoundError` hierarchy |
| `app/data_providers/models.py` | `TickerInfo`, `PriceBar`, `Fundamentals` Pydantic value objects |
| `app/data_providers/base.py` | `MarketDataProvider` ABC, `FundamentalsProvider` ABC |
| `app/data_providers/yfinance_provider.py` | `YFinanceProvider` — wraps yfinance via `asyncio.to_thread`; NaN→None |
| `app/data_providers/polygon_provider.py` | `PolygonProvider` stub — satisfies ABCs, raises `NotImplementedError` |
| `tests/conftest.py` | Shared fixtures: `client` (sync `TestClient`), `async_client` (httpx) |
| `tests/test_health.py` | 5 tests covering `/health` shape and invariants |
| `tests/data_providers/test_yfinance_provider.py` | 7 tests — mocked yfinance; happy paths + TickerNotFoundError + NaN mapping |
| `tests/data_providers/test_polygon_provider.py` | 6 tests — ABC contract + NotImplementedError on all methods |
| `alembic/env.py` | Async migration runner; reads `DATABASE_URL` from `AppSettings` |
| `alembic/versions/20260522_…_initial.py` | Empty initial revision |
| `app/models/ticker.py` | `Ticker` ORM model — `tickers` table; symbol, name, exchange, asset_type, sector, industry |
| `app/models/price_bar.py` | `PriceBar` ORM model — `price_bars` table; OHLCV + adjusted_close; unique (ticker_id, ts, interval) |
| `app/models/fundamentals.py` | `Fundamentals` ORM model — `fundamentals` table; snapshot per (ticker_id, as_of) |
| `app/repositories/__init__.py` | Barrel export: `TickerRepository`, `PriceRepository` |
| `app/repositories/ticker_repository.py` | `TickerRepository` — get_by_symbol, get_by_id, upsert, search |
| `app/repositories/price_repository.py` | `PriceRepository` — upsert_bars (idempotent), get_bars (date+interval filter) |
| `alembic/versions/20260601_b3f8a2c19d04_add_ticker_pricebar_fundamentals.py` | Migration: creates tickers, price_bars, fundamentals tables + indexes |
| `tests/repositories/conftest.py` | Async SQLite in-memory fixtures: `async_engine`, `db_session` |
| `tests/repositories/test_ticker_repository.py` | 10 tests — upsert, get_by_symbol/id, search (prefix + case-insensitive + limit) |
| `tests/repositories/test_price_repository.py` | 6 tests — upsert idempotency, range query, interval filter |
| `pyproject.toml` | uv project; runtime + dev deps; ruff/black/mypy/pytest config |

| `app/api/v1/tickers.py` | `GET /tickers/search?q=` + `GET /tickers/{symbol}` + `GET /tickers/{symbol}/prices`; full set of Pydantic response models including `PriceBarItem` + `PriceBarPageResponse` |
| `tests/test_tickers.py` | 8 endpoint tests with SQLite `get_db` override; covers search, case-insensitivity, 404, 422 |

| `app/workers/__init__.py` | Barrel export for `celery_app` |
| `app/workers/celery_app.py` | `make_celery()` factory + module-level `celery_app`; JSON serialization; Redis fallback; full beat_schedule (daily_prices, quarterly_fundamentals, corporate_actions_sync) |
| `app/workers/tasks/daily_prices.py` | `run_daily_prices` task — fetches yesterday's OHLCV for all active tickers via YFinanceProvider, upserts via PriceRepository. Fires at 18:00 UTC daily. |
| `app/workers/tasks/quarterly_fundamentals.py` | `run_quarterly_fundamentals` task — fetches today's fundamentals for all active tickers. Fires every Monday at 07:00 UTC. |
| `app/workers/tasks/corporate_actions_sync.py` | `run_corporate_actions_sync` task — syncs splits + dividends, recomputes adjusted_close only for newly inserted splits. Fires every Monday at 06:00 UTC. |
| `alembic/versions/20260607_…_convert_price_bars_hypertable.py` | Migration: drops surrogate id, creates natural PK (ticker_id, timestamp, interval), calls `create_hypertable` |
| `alembic/versions/20260609_c7e4f1a2b903_add_corporate_actions.py` | Migration: creates corporate_actions table with unique constraint (ticker_id, action_type, ex_date) |
| `app/models/corporate_action.py` | `CorporateAction` ORM model — splits and dividends with unique constraint for idempotent upsert |
| `app/repositories/corporate_action_repository.py` | `CorporateActionRepository` — upsert (idempotent), get_by_ticker (with optional since filter) |
| `app/repositories/fundamentals_repository.py` | `FundamentalsRepository` — upsert (idempotent on ticker_id + as_of), get_latest |
| `app/data_providers/models.py` | `CorporateActionDTO` added alongside TickerInfo, PriceBar, Fundamentals |
| `scripts/backfill.py` | CLI: `--years N --symbols A,B --dry-run --delay`. Idempotent backfill of OHLCV history. |
| `backend/Dockerfile` | Multi-stage build (uv); used by worker and beat services in docker-compose |

**Runtime deps:** `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `structlog`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `yfinance`, `celery[redis]`, `redis`
**Dev deps:** `pytest`, `pytest-asyncio`, `httpx`, `pre-commit`, `ruff`, `black`, `mypy`, `aiosqlite`

### Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `app/layout.tsx` | Root layout — Geist font, Stockie AI metadata |
| `app/page.tsx` | Sprint 0 placeholder page |
| `components/ui/button.tsx` | shadcn/ui Button component (base-ui primitive + CVA variants) |
| `lib/utils.ts` | `cn()` helper — Tailwind class merge utility |
| `lib/api/schema.d.ts` | Auto-generated TypeScript types from `/openapi.json` (run `npm run generate`) |
| `lib/api/client.ts` | `apiClient` singleton — openapi-fetch typed against `paths` |
| `lib/api/index.ts` | Barrel re-export: `apiClient`, `components`, `paths`, `operations` |
| `components/health-status.tsx` | Async server component: fetches `/health`, renders status card + skeleton |
| `types/css.d.ts` | Ambient CSS module declaration (silences IDE false-positive on CSS side-effect imports) |

| `components/ticker-result-item.tsx` | `TickerResultItem` — symbol chip, name, asset-type badge (color-coded), exchange |
| `components/ticker-search-bar.tsx` | `TickerSearchBar` — debounced (300ms), keyboard nav (↑↓Enter Esc), ARIA combobox |
| `app/tickers/[symbol]/page.tsx` | Ticker detail page — server component; metadata card + 3 placeholder sections |
| `lib/api/schema.d.ts` | Extended with `/tickers/search` + `/tickers/{symbol}` paths + `TickerSearchResult/Response` schemas |

**Stack:** Next.js 14.2 (App Router) + TypeScript + Tailwind CSS + ESLint + Prettier + shadcn/ui

### Infrastructure (`infra/`)

| File | Purpose |
|------|---------|
| `docker-compose.yml` | `stockie_db` (TimescaleDB pg16) + `stockie_redis` (Redis 7 Alpine) |
| `postgres/init/01_extensions.sql` | `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE` |
| `.env.example` | Postgres + Redis credentials/ports with dev defaults |

### Root

| File | Purpose |
|------|---------|
| `.pre-commit-config.yaml` | trailing-whitespace, EOF, YAML/TOML, ruff, black, mypy (all scoped to `backend/`) |

---

## How to run

```bash
# First-time setup
cp backend/.env.example backend/.env
cp infra/.env.example infra/.env
cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]"
pre-commit install           # from repo root

# Daily dev
cd infra && docker compose up -d                            # TimescaleDB + Redis
cd backend && uv run uvicorn app.main:app --reload          # http://localhost:8000
cd frontend && npm run dev                                  # http://localhost:3000

# Tests / linting
cd backend && uv run pytest -v
pre-commit run --all-files

# Migrations (DB must be running)
cd backend && uv run alembic upgrade head
cd backend && uv run alembic revision --autogenerate -m "<message>"
```

---

## Locked architectural decisions

| Decision | Detail |
|----------|--------|
| Package managers | **uv** (backend), **npm** (frontend) |
| DB driver | Always `postgresql+asyncpg://…` — never sync `postgresql://` |
| Config | Always `get_settings()` — never instantiate `AppSettings` directly |
| Alembic URL | Read from `AppSettings` in `env.py` — never hardcode in `alembic.ini` |
| File headers | Every authored file gets the JSDoc/docstring header (CLAUDE.md §File-Level Documentation) |
| Recommendation engine | Rules-based for MVP; ML/LLM is post-MVP |
| Monetization | None during the build phase |
| Launch market | US equities + ETFs first; BVL (Peru) deferred to v1.1 |

---

## Team split

- **@bvela (Bryan)** → backend: Python, FastAPI, data, scoring, migrations
- **@despinoza** → frontend: Next.js, React, charts, UX
- **@both** → tasks requiring a pair session

---

## Next sprint preview

**Sprint 2 (Weeks 5–6) — BACKEND COMPLETE:** All backend tasks done (Tasks 1–9 ✅). Three frontend tasks remain for @despinoza (Tasks 10–12: TradingView charts, timeframe toggle, data-as-of badge). See `.claude/plans/sprint2-prices-api-and-frontend.md` for the frontend plan.
