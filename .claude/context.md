# Stockie AI — Cold-Start Context

> **For Claude:** Read this file at the start of every conversation before taking any action.
> **Update rule:** After every completed sprint task, mark it ✅ here and update the "What has been built" table.
> Full backlog → `docs/PLANNING_tasks.md` | Feature plan → `docs/PLANNING_features.md`

---

## Active sprint: Sprint 3 — Fundamental analysis module (Weeks 7–8)

**Goal:** A ticker shows a full fundamentals view with a 0–100 fundamental score broken into Value / Quality / Growth.

### Checklist (Sprint 3-A — metrics + scoring engine)

| # | Status | Owner | Task |
|---|--------|-------|------|
| A1 | ✅ | @bvela | `FinancialStatement` ORM model + Alembic migration |
| A2 | ✅ | @bvela | `AnnualFinancials` DTO + `get_annual_financials()` in providers |
| A3 | ✅ | @bvela | `FinancialStatementRepository` (upsert + history) |
| A4 | ✅ | @bvela | Ingest annual statements in `quarterly_fundamentals` beat task |
| A5 | ✅ | @bvela | `services/fundamentals/ratios.py` — valuation ratio calculators |
| A6 | ✅ | @bvela | `services/fundamentals/quality.py` — quality metric calculators |
| A7 | ✅ | @bvela | `services/fundamentals/growth.py` — CAGR growth calculators |
| A8 | ✅ | @bvela | `scoring/fundamental.py` — subscores + overall (WEIGHTS_VERSION v1.0) |
| A9 | ✅ | @bvela | Golden-number tests for AAPL fixture (`tests/scoring/test_golden_aapl.py`) |

### Checklist (Sprint 3-B — API + caching, upcoming)

| # | Status | Owner | Task |
|---|--------|-------|------|
| B1 | [ ] | @bvela | Simplified DCF endpoint with adjustable assumptions |
| B2 | [ ] | @bvela | Peer-comparison endpoint (3–5 peers by sector + market-cap bucket) |
| B3 | [ ] | @bvela | Cache fundamental scores in Redis (daily TTL) |
| B4 | [ ] | @despinoza | Fundamentals tab: ratios table, subscore bar chart, peer comparison |
| B5 | [ ] | @despinoza | Interactive DCF widget (sliders → live recalc) |
| B6 | [ ] | @despinoza | Score badge component (0–100 visual, reused across modules) |

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

| `app/models/financial_statement.py` | `FinancialStatement` ORM model — one row per `(ticker_id, fiscal_year, period_type)`; income + balance + cashflow line items |
| `alembic/versions/20260612_d4e8b1f9a205_add_financial_statements.py` | Migration: creates `financial_statements` table with FK, unique constraint, index |
| `app/data_providers/models.py` | `AnnualFinancials` Pydantic DTO added (all statement line items) |
| `app/data_providers/yfinance_provider.py` | `get_annual_financials()` added; `_row()` multi-label fallback helper for yfinance label quirks |
| `app/repositories/financial_statement_repository.py` | `FinancialStatementRepository` — idempotent `upsert()`, `get_history()` ordered newest-first |
| `app/services/__init__.py` + `app/services/fundamentals/__init__.py` | Package init files for pure services layer (no DB, no network) |
| `app/services/fundamentals/ratios.py` | `ValuationRatios` dataclass + calculators: pe, pb, ps, ev_ebitda, dividend_yield, peg |
| `app/services/fundamentals/quality.py` | `QualityMetrics` dataclass + calculators: ROE, ROIC, margins, D/E, interest coverage; `DEFAULT_TAX_RATE = 0.21` |
| `app/services/fundamentals/growth.py` | `GrowthMetrics` dataclass + calculators: revenue/EPS/FCF CAGR 1Y/3Y/5Y; `_best_effort_5y()` degrades gracefully |
| `app/scoring/__init__.py` | Package init for scoring module |
| `app/scoring/fundamental.py` | `FundamentalScore`, `normalize()`, `score_value/quality/growth()`, `score_fundamental()`; `WEIGHTS_VERSION = "v1.0"` |
| `tests/fixtures/aapl_fundamentals.json` | Frozen AAPL fixture (FY2021–FY2024 + TTM snapshot) with golden scores for determinism contract |
| `tests/scoring/test_fundamental.py` | 20 unit tests: normalize, renormalization, monotonicity, score_fundamental |
| `tests/scoring/test_golden_aapl.py` | 8 golden-number tests: full pipeline on AAPL fixture, ±1.0 tolerance on subscores + overall |
| `tests/repositories/test_financial_statement_repository.py` | 6 repo tests: upsert, idempotency, update, ordering, limit, empty |
| `tests/services/fundamentals/test_ratios.py` | 18 ratio tests |
| `tests/services/fundamentals/test_quality.py` | 26 quality tests |
| `tests/services/fundamentals/test_growth.py` | 14 growth tests |

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
| `app/tickers/[symbol]/page.tsx` | Ticker detail page — server component; metadata card + price section client island |
| `lib/api/schema.d.ts` | All paths + schemas: search, detail, prices (`PriceBarItem`, `PriceBarPageResponse`) |
| `lib/types/timeframe.ts` | `Timeframe` union type + `timeframeToDateRange()` helper |
| `components/timeframe-toggle.tsx` | 7-button segmented toggle (1D/1W/1M/3M/1Y/5Y/Max) |
| `components/data-as-of-badge.tsx` | Muted freshness badge; renders "Data unavailable" fallback when null |
| `components/price-chart.tsx` | TradingView Lightweight Charts v5 candlestick chart; loading skeleton + empty state |
| `components/ticker-price-section.tsx` | Client island: fetches prices, composes chart + toggle + badge |

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

**Sprint 2 (Weeks 5–6) — COMPLETE ✅:** All 12 tasks done. Backend ingestion pipeline, prices API endpoint, and frontend chart UI fully implemented.

**Sprint 3-A (Weeks 7–8) — COMPLETE ✅:** All 9 tasks done. Annual financial-statement storage, pure metric calculators (ratios/quality/growth), deterministic scoring engine (WEIGHTS_VERSION v1.0), and AAPL golden-number tests. 187 tests green, pre-commit clean.

**Sprint 3-B (next):** DCF endpoint, peer-comparison endpoint, Redis caching, and the Fundamentals tab + DCF widget UI.
