# Stockie AI — Task Plan (Living Document)

Companion to [`PLANNING_features.md`](./PLANNING_features.md). This is the working backlog. **Edit it.** Tick boxes as we complete tasks, append to the Decision Log when we change direction, add to the Risks section when we hit something unexpected.

---

## 0. How to use this file

- **Checkboxes** (`- [ ]` → `- [x]`) are the source of truth for progress. Don't delete completed tasks; we want the history.
- **Owners** are tagged inline: `@bvela` (backend) or `@despinoza` (frontend). `@both` means we pair on it.
- **Statuses** beyond checkbox: add `(WIP)`, `(BLOCKED: reason)`, or `(DEFERRED: reason)` after a task when relevant.
- **Adding tasks**: append to the current sprint or to the backlog at the bottom. Don't rewrite history.
- **When a sprint ends**: write a 2-3 line retro under that sprint's "Retro" subsection. What shipped, what slipped, what to change.
- **When we change a major decision**: log it in section 7 with a date. Don't just edit and forget.

---

## 1. Locked-in decisions (from feature-planning review)

| #   | Decision                                                                                                          | Rationale                                                                               |
| --- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| D1  | **Launch market: US equities + ETFs first.** BVL ships in v1.1.                                                   | Data availability and tooling maturity. BVL is differentiator, not blocker.             |
| D2  | **Single tier during build; no monetization work.**                                                               | Skip Stripe, billing, paid-tier gating until we have users.                             |
| D3  | **LLM API dependency is acceptable.**                                                                             | Use OpenAI/Anthropic for sentiment scoring and chat assistant when those features land. |
| D4  | **Rules-based recommendation engine for MVP.** ML/LLM scoring is post-MVP.                                        | Transparency, regulatory safety, lower delivery risk.                                   |
| D5  | **Backend/frontend split:** `@bvela` owns Python/FastAPI/data/scoring; `@despinoza` owns Next.js/React/charts/UX. | Plays to existing strengths.                                                            |
| D6  | **Cadence: 2-week sprints, ~10 hrs/week each (~40 hrs per sprint combined).** MVP target ≈ 5 months / 10 sprints. | Realistic part-time pace.                                                               |
| D7  | **Python 3.12 + FastAPI + Postgres/TimescaleDB + Redis + Next.js + TypeScript.**                                  | See PLANNING_features.md §5.                                                            |

---

## 2. Project conventions

- **Repo layout** (assumed; revisit in Sprint 0):
  ```
  stockie_ai/
    backend/        # FastAPI app, services, models, repositories
      app/
        api/        # FastAPI routers
        services/   # business logic
        models/     # SQLAlchemy / Pydantic
        repositories/
        data_providers/  # provider abstractions (yfinance, Polygon, ...)
        scoring/    # fundamental, technical, sentiment, macro, recommendation
        workers/    # Celery tasks
        core/       # config, db, security
      tests/
    frontend/       # Next.js app
      app/
      components/
      lib/
    infra/          # docker-compose, deploy configs
    PLANNING_features.md
    PLANNING_tasks.md   # this file
    CLAUDE.md
  ```
- **Branches:**
  - `main` — always deployable; no direct pushes.
  - `feat/<short-desc>` — new features (e.g. `feat/ticker-search`).
  - `fix/<short-desc>` — bug fixes (e.g. `fix/health-timestamp-tz`).
  - `chore/<short-desc>` — tooling, deps, config (e.g. `chore/upgrade-ruff`).
  - `docs/<short-desc>` — documentation-only changes.
  - Keep names lowercase, hyphen-separated, ≤ 40 characters.
  - Open a PR against `main`; the other person reviews before merge.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `test:`, `docs:`).
- **Issues:** Use the GitHub issue templates (bug report / feature request). Link issues to PRs with `Closes #<n>`.
- **PRs:** Use the PR template. CI must be green before merge. Squash-merge preferred to keep `main` history clean.
- **Definition of Done** (every task):
  1. Code merged to `main` via reviewed PR.
  2. Passing tests where applicable (unit for backend logic, component/e2e for frontend flows).
  3. File headers updated per `CLAUDE.md` (every file we touch).
  4. Public functions/components have docstrings/JSDoc.
  5. No secrets in code; new env vars added to `.env.example` and documented.
  6. If user-facing: works on desktop Chrome at minimum, basic responsive check.

---

## 3. Milestones at a glance

| Milestone                       | Target sprint    | What "done" looks like                                                          |
| ------------------------------- | ---------------- | ------------------------------------------------------------------------------- |
| **M0 — Scaffold ready**         | End of Sprint 0  | Repos, CI, local dev, "hello world" full-stack request works.                   |
| **M1 — Data layer live**        | End of Sprint 2  | US OHLCV + fundamentals ingest daily into Postgres; ticker search works.        |
| **M2 — Single-ticker analysis** | End of Sprint 4  | A ticker detail page shows fundamentals + technicals + chart for any US ticker. |
| **M3 — Recommendations**        | End of Sprint 6  | Rule-based, horizon-aware recommendations with explanations and disclaimer.     |
| **M4 — Users & portfolios**     | End of Sprint 7  | Auth, watchlists, portfolios, basic alerts.                                     |
| **M5 — Beta-ready**             | End of Sprint 8  | Polished dashboard, e2e tests, deployable to staging.                           |
| **M6 — v1.0 public**            | End of Sprint 10 | Public launch on US equities + ETFs. BVL groundwork started.                    |

---

## 4. Sprint backlog

> Each sprint is two weeks. Owners are placeholders — swap freely. Don't be precious about scope; if something slips, move it to the next sprint and log it in the retro.

### Sprint 0 — Scaffolding (Weeks 1–2)

**Goal:** Both of us can run the full stack locally and push to a shared repo. No business logic yet.

- [x] `@bvela` Create GitHub repo, add `CLAUDE.md`, `PLANNING_features.md`, `PLANNING_tasks.md`, `.gitignore`, `LICENSE`.
- [x] `@bvela` Initialize FastAPI project with Poetry/uv, Pydantic Settings, `/health` endpoint, structured logging.
- [x] `@bvela` Add `docker-compose.yml` with Postgres + TimescaleDB extension + Redis.
- [x] `@bvela` Configure Alembic migrations; create an empty initial migration.
- [x] `@bvela` Set up pre-commit (ruff + black + mypy) and pytest skeleton.
- [x] `@despinoza` Initialize Next.js 14 + TypeScript + Tailwind project.
- [x] `@despinoza` Set up ESLint + Prettier + a basic component library (shadcn/ui or similar).
- [x] `@despinoza` Wire a typed API client (e.g. `openapi-typescript`) consuming FastAPI's `/openapi.json`.
- [x] `@despinoza` Build placeholder landing page that calls `/health` and renders the response.
- [x] `@both` GitHub Actions CI: lint + tests on every PR, both backend and frontend.
- [x] `@both` Decide on issue/PR template and branch naming. Document under §2.
- [x] `@both` Pair session: end-to-end smoke (`docker compose up` → both services reachable, frontend reads from backend).

**Retro (fill at end of sprint):**

> _What shipped:_
> _What slipped:_
> _What to change:_

---

### Sprint 1 — Data provider abstractions + ticker resolution (Weeks 3–4)

**Goal:** Backend can resolve US tickers and fetch OHLCV/fundamentals via a provider-agnostic interface. Frontend can search tickers.

- [x] `@bvela` Design `MarketDataProvider` and `FundamentalsProvider` abstract interfaces (per Dependency Inversion).
- [x] `@bvela` Implement `YFinanceProvider` as the first concrete provider.
- [x] `@bvela` Stub a second provider (`PolygonProvider`) with NotImplemented to prove the abstraction holds.
- [x] `@bvela` Define `Ticker`, `PriceBar`, `Fundamentals` SQLAlchemy models + migrations.
- [x] `@bvela` Repository pattern: `TickerRepository`, `PriceRepository`.
- [x] `@bvela` `GET /tickers/search?q=` endpoint (prefix + fuzzy match on symbol & name).
- [x] `@bvela` Unit tests for providers (with mocked HTTP) and search endpoint.
- [x] `@despinoza` Global search bar component with debounced query against `/tickers/search`.
- [x] `@despinoza` Ticker result list UI (symbol, name, exchange, asset type chip).
- [x] `@despinoza` Ticker detail page skeleton (route: `/tickers/[symbol]`), shows raw data for now.
- [x] `@both` Decide initial ticker universe size (top N S&P500 + top M ETFs for week-1 ingest). Log under §7.

**Retro:**

> _What shipped:_ Full provider abstraction layer (MarketDataProvider, FundamentalsProvider ABCs; YFinanceProvider; PolygonProvider stub). SQLAlchemy ORM models (Ticker, PriceBar, Fundamentals) + hand-written Alembic migration. TickerRepository + PriceRepository with SQLite-based unit tests. GET /tickers/search and GET /tickers/{symbol} endpoints (42 tests green). Frontend: TickerSearchBar (debounced, keyboard nav, ARIA), TickerResultItem, ticker detail page skeleton at /tickers/[symbol].
> _What slipped:_ Nothing — all 11 tasks completed.
> _What to change:_ Pre-commit mypy hook caught a name-collision bug (`import app.models` shadowing `from app.main import app`) that tests didn't catch. Add mypy to the local dev check step before committing.

---

### Sprint 2 — Ingestion pipeline + price storage (Weeks 5–6)

**Goal:** Scheduled jobs pull daily OHLCV and quarterly fundamentals into Postgres. Time-series queries are fast.

- [x] `@bvela` Add Celery + Redis broker; one worker container in `docker-compose`.
- [x] `@bvela` `daily_prices` Celery beat task: fetch + upsert OHLCV for all tracked tickers.
- [x] `@bvela` `quarterly_fundamentals` Celery beat task: pull income/balance/cashflow + key ratios.
- [x] `@bvela` Backfill script: load N years of history for the initial universe.
- [x] `@bvela` Convert `price_bars` table to TimescaleDB hypertable; add compound index `(ticker_id, timestamp)`.
- [x] `@bvela` `GET /tickers/{symbol}/prices?timeframe=1d&from=...&to=...` endpoint with sane pagination/limits.
- [x] `@bvela` Corporate-actions handling: store splits and dividends, expose adjusted-close.
- [x] `@bvela` "As-of" timestamp threaded through every endpoint response.
- [x] `@bvela` Tests: ingestion idempotency (re-run doesn't duplicate), split-adjustment correctness.
- [x] `@despinoza` Integrate TradingView Lightweight Charts (or chosen lib) on the ticker page.
- [x] `@despinoza` Timeframe toggle (1D/1W/1M/3M/1Y/5Y/Max) hitting the prices endpoint.
- [x] `@despinoza` "Data as of" badge component, used across the app.
- [x] `@both` Pair on at least one tricky bug; document any provider quirks in `backend/app/data_providers/README.md`.

**Retro:**

> _What shipped:_ All 13 tasks completed. Full ingestion pipeline: Celery + Redis, daily OHLCV and quarterly fundamentals beat tasks, corporate-actions sync (splits + dividends with adjusted-close recomputation), TimescaleDB hypertable conversion, backfill CLI, `GET /tickers/{symbol}/prices` with keyset cursor pagination. Frontend: TradingView Lightweight Charts v5 candlestick chart, timeframe toggle (1D–Max), DataAsOf badge, and TickerPriceSection client island. Provider quirks documented in `backend/app/data_providers/README.md`; tricky bug: `auto_adjust=False` required to separate raw close from adjusted close, plus a `"Adj Close" in df.columns` guard for tickers where Yahoo omits the adjusted series entirely.
> _What slipped:_ Nothing.
> _What to change:_ `lib/api/schema.d.ts` is manually maintained because `npm run generate` requires the backend server to be running locally. Add a CI step that starts the server, runs `npm run generate`, and fails if the generated output differs from the committed file.

---

### Sprint 3 — Fundamental analysis module (Weeks 7–8)

**Goal:** A ticker shows a full fundamentals view with a 0–100 fundamental score broken into Value / Quality / Growth.

- [x] `@bvela` Implement ratio calculations: P/E, P/B, P/S, EV/EBITDA, PEG, dividend yield.
- [x] `@bvela` Implement quality metrics: ROE, ROIC, margins, debt/equity, interest coverage.
- [x] `@bvela` Implement growth metrics: revenue/EPS/FCF CAGR (1Y/3Y/5Y).
- [x] `@bvela` `scoring/fundamental.py`: deterministic, documented weighting → Value/Quality/Growth subscores + overall.
- [x] `@bvela` Simplified DCF endpoint with adjustable assumptions (growth, discount, terminal).
- [x] `@bvela` Peer-comparison endpoint: auto-pick 3–5 peers by sector + market-cap bucket.
- [x] `@bvela` Cache fundamental scores in Redis with a daily TTL.
- [x] `@bvela` Unit tests with golden numbers for known tickers (AAPL FY2021–2024, 228 tests green).
- [x] `@bvela` Fundamentals tab on ticker page: ratios table, subscore bar chart, peer comparison table.
- [x] `@bvela` Interactive DCF widget (sliders → live recalc via endpoint).
- [x] `@bvela` Score badge component (consistent 0–100 visual, reused across modules).

**Retro:**

> _What shipped:_ Full fundamental analysis pipeline (backend + frontend). 228 tests, ScoreBadge, SubscoreChart, PeerComparisonTable, Slider, DcfWidget, FundamentalsSection, TickerTabs. Lint + build clean.
> _What slipped:_ Nothing.
> _What to change:_ —

---

### Sprint 4 — Technical analysis module (Weeks 9–10)

**Goal:** A ticker shows technical indicators, S/R levels, and a 0–100 technical score.

- [ ] `@bvela` Integrate `pandas-ta` (preferred over TA-Lib for install simplicity).
- [ ] `@bvela` Indicator endpoints: SMA/EMA, RSI, MACD, Bollinger, ATR — query-string driven.
- [ ] `@bvela` Rule-based support/resistance detection (pivot points + clustering).
- [ ] `@bvela` `scoring/technical.py`: trend strength + momentum + mean-reversion → 0–100.
- [ ] `@bvela` Multi-timeframe aggregator (daily/weekly/monthly resampling, cached).
- [ ] `@bvela` Tests on synthetic price series with known patterns (uptrend, breakout, reversal).
- [ ] `@despinoza` Technicals tab: indicator overlays on chart, RSI/MACD subpanes, S/R level lines.
- [ ] `@despinoza` Indicator settings drawer (toggle/configure indicators per chart).
- [ ] `@despinoza` Timeframe selector wired to multi-timeframe endpoint.
- [ ] `@both` Define how Fundamental and Technical scores combine (preview of recommendation engine logic). Log under §7.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 5 — News, sentiment & macro/sector module (Weeks 11–12)

**Goal:** A ticker has a sentiment score backed by recent news. The macro dashboard shows US (and Peru placeholder) macro indicators.

- [ ] `@bvela` News ingestion worker: pull RSS + free news APIs into a `news_articles` table.
- [ ] `@bvela` Article → ticker linking (symbol + company-name matching with confidence).
- [ ] `@bvela` Sentiment scoring: FinBERT locally as default, LLM API fallback (per D3) for ambiguous cases.
- [ ] `@bvela` Per-ticker rolling sentiment score (-100..+100) with decay over time.
- [ ] `@bvela` `/tickers/{symbol}/news` + `/tickers/{symbol}/sentiment` endpoints.
- [ ] `@bvela` Macro data ingest: FRED for US (rates, CPI, GDP, unemployment); placeholder source for Peru.
- [ ] `@bvela` Sector heatmap endpoint (11 GICS sectors, performance + valuation + momentum).
- [ ] `@bvela` Tests: sentiment determinism on a fixed sample; macro endpoint shape.
- [ ] `@despinoza` News & sentiment tab on ticker page: article list, sentiment trendline, source filter.
- [ ] `@despinoza` Macro dashboard page (US): rate curve, CPI/GDP trends, key indices.
- [ ] `@despinoza` Sector heatmap component on landing page.
- [ ] `@both` Decide LLM provider for sentiment fallback (Anthropic vs OpenAI) and how to budget cost. Log under §7.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 6 — Recommendation engine + ticker page assembly (Weeks 13–14)

**Goal:** Every ticker has a recommendation card showing short/mid/long-term verdicts with explanations and the four sub-scores. Ticker page is feature-complete for MVP.

- [ ] `@bvela` `scoring/recommendation.py`: combines Fundamental/Technical/Sentiment/Macro into per-horizon verdicts.
- [ ] `@bvela` Horizon-specific weight tables (configurable, version-controlled). Long-term leans fundamental, short-term leans technical+sentiment.
- [ ] `@bvela` Plain-language explanation generator (template-based; LLM polishing optional).
- [ ] `@bvela` `/tickers/{symbol}/recommendation` endpoint returning all three horizons + confidence + disclaimer text.
- [ ] `@bvela` Recommendation snapshot table (history of recommendations over time, for future backtesting).
- [ ] `@bvela` Tests: scoring monotonicity (if a subscore drops, overall doesn't increase, etc.).
- [ ] `@despinoza` Recommendation card component (top of ticker page): three horizon chips, action, confidence, sub-scores, explanation, disclaimer.
- [ ] `@despinoza` Ticker detail page final layout: header + recommendation card + four tabs (Fundamental, Technical, News/Sentiment, Macro context).
- [ ] `@despinoza` Empty/loading/error states across all modules.
- [ ] `@both` Code review pass on the entire scoring pipeline.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 7 — Accounts, watchlists, portfolios, alerts (Weeks 15–16)

**Goal:** Users can sign up, save tickers, track positions, and get notified.

- [ ] `@bvela` Auth: email/password + Google OAuth (Authlib). JWT-based session.
- [ ] `@bvela` `users`, `watchlists`, `watchlist_items` tables and CRUD endpoints (per-user isolation).
- [ ] `@bvela` `portfolios`, `positions`, `transactions` tables + CRUD endpoints.
- [ ] `@bvela` Portfolio analytics: total return, time-weighted return, allocation by sector/region/asset type.
- [ ] `@bvela` USD↔PEN FX revaluation (FX rates ingested in Sprint 2; ensure daily snapshot).
- [ ] `@bvela` Alert rules table; rule engine for price + RSI/MACD alerts.
- [ ] `@bvela` Email delivery (Postmark/SES/Resend) for triggered alerts.
- [ ] `@bvela` Tests: auth flow, per-user isolation enforced (security-critical), portfolio math.
- [ ] `@despinoza` Sign up / login / reset-password screens.
- [ ] `@despinoza` Watchlist UI: add/remove tickers, drag to reorder, multiple watchlists.
- [ ] `@despinoza` Portfolio UI: position entry form, holdings table, returns chart, allocation breakdown.
- [ ] `@despinoza` Alert creation modal + alerts list page.
- [ ] `@both` Threat-model the auth surface (session handling, password reset tokens, rate limiting).

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 8 — Dashboard, polish, e2e tests (Weeks 17–18)

**Goal:** Landing dashboard ties it together. Performance and reliability tightened.

- [ ] `@bvela` `/dashboard/summary` endpoint: portfolio status + watchlist movers + top recommendations today + macro snapshot, fully cached.
- [ ] `@bvela` Pre-compute scores nightly so dashboard loads instantly.
- [ ] `@bvela` Add request rate limiting (per IP and per user).
- [ ] `@bvela` Sentry (or alternative) for error tracking, both backend and worker.
- [ ] `@bvela` Performance pass: target p95 < 500ms for cached endpoints.
- [ ] `@despinoza` Landing dashboard layout: hero with portfolio summary, watchlist movers carousel, top picks grid, macro strip.
- [ ] `@despinoza` Dark mode polish; loading skeletons everywhere; error toasts.
- [ ] `@despinoza` Playwright e2e tests for the critical flows: sign up → add watchlist → view recommendation → set alert.
- [ ] `@despinoza` Accessibility pass (keyboard nav, contrast, labels).
- [ ] `@both` Bug bash: each of us spends a full session trying to break the other's work.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 9 — Closed beta (Weeks 19–20)

**Goal:** Real users (~10 friends) on a staging deploy. Iterate on feedback.

- [ ] `@bvela` Production-like deploy: staging environment on chosen host (Fly.io / Render / AWS).
- [ ] `@bvela` Backups configured for Postgres; restore drill performed.
- [ ] `@bvela` Document `infra/` setup so either of us can redeploy from scratch.
- [ ] `@bvela` Address backend bugs from beta feedback.
- [ ] `@despinoza` Onboarding flow (3-step first-run tour).
- [ ] `@despinoza` Feedback widget in the app pointing to a shared inbox.
- [ ] `@despinoza` Address UX bugs from beta feedback.
- [ ] `@both` Invite ~10 testers, collect structured feedback (Google Form linked from app).
- [ ] `@both` Decide v1.0 launch readiness gate. Log under §7.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

### Sprint 10 — v1.0 launch + v1.1 BVL groundwork (Weeks 21–22)

**Goal:** Public release. Start BVL pipeline in parallel.

- [ ] `@bvela` Final security pass (deps audit, secret scan, headers).
- [ ] `@bvela` Production deploy + monitoring dashboards.
- [ ] `@bvela` Prototype BVL scraper for `bvl.com.pe` price data (research spike — feasibility report, not full pipeline).
- [ ] `@bvela` Decide on a paid BVL data source if scraping is too fragile. Log under §7.
- [ ] `@despinoza` Marketing landing page (separate from app dashboard).
- [ ] `@despinoza` Spanish localization scaffolding (i18n library, top-level UI strings — full translation in v1.1).
- [ ] `@despinoza` Analytics (privacy-friendly, e.g. Plausible).
- [ ] `@both` Public launch announcement.
- [ ] `@both` Plan v1.1: BVL coverage, Spanish UI, social signals (Reddit), backtesting.

**Retro:**

> _What shipped:_ _What slipped:_ _What to change:_

---

## 5. Post-MVP backlog (v1.1+)

> Pull from here only after the previous sprint's must-haves are done. Rough priority order, not strict.

- [ ] **BVL ingestion pipeline** (scheduled scraper + manual fundamentals for top ~50 tickers).
- [ ] **Spanish localization** of the full UI.
- [ ] **Reddit & social sentiment** (r/stocks, r/investing, r/wallstreetbets mention volume + sentiment).
- [ ] **Backtesting engine** with realistic transaction costs and slippage.
- [ ] **LLM chat assistant** (RAG over our structured data + tool use to call scoring endpoints).
- [ ] **Earnings calendar & event tracker.**
- [ ] **ML recommendation layer** (gradient boosting first; presented alongside rules, never replacing).
- [ ] **Paper trading** with live prices.
- [ ] **Strategy builder** (no-code visual signal builder).
- [ ] **Insider trading & 13F data** (US first).
- [ ] **Tax reporting helpers** (US 1099-style, Peru SUNAT-aligned).
- [ ] **Crypto coverage.**
- [ ] **Broker integration** (Alpaca/IBKR for US first). Behind compliance feature flag.
- [ ] **Mobile app or PWA.**
- [ ] **Community features** (shared watchlists, model portfolios). Only after PMF.

---

## 6. Risks & blockers (running log)

| Date       | Risk / Blocker                                                            | Severity | Owner  | Mitigation / status                                                                                              |
| ---------- | ------------------------------------------------------------------------- | -------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| 2026-05-21 | yfinance is unofficial and breaks periodically.                           | Medium   | @bvela | Provider abstraction is non-negotiable; have Polygon (paid) ready as fallback.                                   |
| 2026-05-21 | BVL has no clean free API; scraping is brittle.                           | High     | @bvela | Treat as v1.1 scope; spike feasibility in Sprint 10.                                                             |
| 2026-05-21 | LLM API costs can balloon for sentiment.                                  | Medium   | @bvela | Default to FinBERT local; LLM only on ambiguous cases; daily spend cap.                                          |
| 2026-05-21 | We are not licensed advisors. Recommendations must be framed as analysis. | High     | @both  | Disclaimer baked into the recommendation card component (Sprint 6); ToS + Privacy Policy before beta (Sprint 9). |
| 2026-05-21 | Two part-time devs ≈ 20 combined hrs/week; sprint slippage is likely.     | Medium   | @both  | Buffer baked into Sprints 8 and 9; willing to cut scope, not quality.                                            |

---

## 7. Decision log

> Append; never delete. Use ISO dates.

- **2026-05-21** — Approved feature plan (PLANNING_features.md). Locked decisions D1–D7 above.
- **2026-05-21** — Backend = bvela, frontend = despinoza. Either may pair on the other's area for hard parts (recommendation engine, BVL ingestion).
- **2026-06-01** — Initial ticker universe for Sprint 2 week-1 ingest: **50 tickers** (45 stocks + 5 ETFs). ETFs: SPY, QQQ, IWM, GLD, TLT. Stocks: 4–5 per GICS sector — IT: AAPL MSFT NVDA AVGO ORCL; Financials: JPM BAC WFC GS; Health Care: UNH JNJ ABBV LLY; Consumer Disc.: AMZN TSLA HD MCD; Industrials: CAT RTX UPS HON; Comm. Services: GOOGL META NFLX DIS; Consumer Staples: PG KO WMT COST; Energy: XOM CVX COP SLB; Real Estate: AMT PLD EQIX O; Materials: LIN APD FCX NEM; Utilities: NEE DUK SO AEP. **This is the seed list only** — the universe is stored in the DB and can be expanded to the full S&P 500 or beyond by inserting more Ticker rows; no code changes needed. Rationale: 50 is small enough for reliable yfinance ingest during Sprint 2 testing and sector-balanced so Sprint 3 peer-comparison has ≥3 neighbors per sector. Approved @both.
- **YYYY-MM-DD** — _Template: brief decision, rationale, who approved._

---

## 8. Pending questions

Things we deferred from the feature-planning round; revisit at the milestone listed.

- [ ] **Hosting & budget** (revisit before Sprint 9 deploy).
- [ ] **BVL data approach**: scrape vs. paid vendor (revisit during Sprint 10 spike).
- [ ] **Monetization model** (revisit after v1.0 launch and ~1 month of usage data).
- [ ] **Self-hostable vs. cloud-LLM** strategy (revisit before chat-assistant work begins post-MVP).
- [ ] **ToS / Privacy Policy** drafting — must be done before Sprint 9 beta.

---

_Keep this file honest. A task plan that doesn't reflect reality is worse than no plan._
