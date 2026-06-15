"""
Description: Tests for FundamentalsService — the orchestrating service that
             assembles ratios, quality, growth, and a FundamentalScore from
             repository data and caches the result via the Redis helper.
             All tests run against an in-memory SQLite DB; the cache is
             replaced with a no-op fake so no Redis connection is needed.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; assembly correctness, cache-hit path, and error cases.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.models.financial_statement import FinancialStatement
from app.models.fundamentals import Fundamentals
from app.models.ticker import Ticker
from app.repositories.financial_statement_repository import (
    FinancialStatementCreate,
    FinancialStatementRepository,
)
from app.repositories.fundamentals_repository import (
    FundamentalsCreate,
    FundamentalsRepository,
)
from app.repositories.ticker_repository import TickerRepository
from app.scoring.fundamental import WEIGHTS_VERSION
from app.services.fundamentals.service import CACHE_TTL_SECONDS, FundamentalsService

# ── DB seeding helpers ────────────────────────────────────────────────────────


async def _seed_ticker(session: AsyncSession) -> Ticker:
    from app.data_providers.models import TickerInfo

    repo = TickerRepository(session)
    return await repo.upsert(
        TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_type="equity",
            currency="USD",
            sector="Technology",
            industry="Consumer Electronics",
        )
    )


async def _seed_snapshot(session: AsyncSession, ticker_id: int) -> Fundamentals:
    repo = FundamentalsRepository(session)
    return await repo.upsert(
        FundamentalsCreate(
            ticker_id=ticker_id,
            as_of=date(2024, 9, 28),
            pe_ratio=Decimal("34.50"),
            pb_ratio=Decimal("60.40"),
            ps_ratio=Decimal("8.95"),
            ev_ebitda=Decimal("27.60"),
            eps_ttm=Decimal("6.08"),
            revenue_ttm=391_035_000_000,
            net_income_ttm=93_736_000_000,
            roe=Decimal("1.47"),
            debt_to_equity=Decimal("150.0"),
            dividend_yield=Decimal("0.0043"),
        )
    )


async def _seed_statement(
    session: AsyncSession, ticker_id: int, fiscal_year: int
) -> FinancialStatement:
    repo = FinancialStatementRepository(session)
    return await repo.upsert(
        FinancialStatementCreate(
            ticker_id=ticker_id,
            fiscal_year=fiscal_year,
            total_revenue=391_035_000_000,
            gross_profit=180_683_000_000,
            operating_income=123_216_000_000,
            net_income=93_736_000_000,
            interest_expense=3_930_000_000,
            eps_diluted=Decimal("6.08"),
            total_assets=364_980_000_000,
            total_equity=56_950_000_000,
            total_debt=96_630_000_000,
            cash_and_equivalents=65_170_000_000,
            operating_cash_flow=118_254_000_000,
            capital_expenditure=-9_447_000_000,
            shares_diluted=15_408_000_000,
        )
    )


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def no_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace cache helpers with no-ops so tests never need Redis."""
    monkeypatch.setattr(
        "app.services.fundamentals.service.cache.get_json", AsyncMock(return_value=None)
    )
    monkeypatch.setattr("app.services.fundamentals.service.cache.set_json", AsyncMock())


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fundamentals_raises_when_ticker_missing(db_session: AsyncSession) -> None:
    """TickerNotFoundError when the symbol does not exist in the DB."""
    service = FundamentalsService(db_session)
    with pytest.raises(TickerNotFoundError):
        await service.get_fundamentals("UNKNOWN")


@pytest.mark.asyncio
async def test_get_fundamentals_raises_when_no_snapshot(db_session: AsyncSession) -> None:
    """TickerNotFoundError when the ticker exists but has no fundamentals snapshot."""
    await _seed_ticker(db_session)
    await db_session.commit()
    service = FundamentalsService(db_session)
    with pytest.raises(TickerNotFoundError):
        await service.get_fundamentals("AAPL")


@pytest.mark.asyncio
async def test_get_fundamentals_returns_result_with_statements(db_session: AsyncSession) -> None:
    """Happy path: ticker + snapshot + statements → FundamentalsResult with scores."""
    ticker = await _seed_ticker(db_session)
    await _seed_snapshot(db_session, ticker.id)
    await _seed_statement(db_session, ticker.id, 2024)
    await db_session.commit()

    service = FundamentalsService(db_session)
    result = await service.get_fundamentals("AAPL")

    assert result.symbol == "AAPL"
    assert result.data_as_of == date(2024, 9, 28)
    assert result.weights_version == WEIGHTS_VERSION
    assert result.score.overall is not None
    assert result.score.value is not None
    assert result.score.quality is not None


@pytest.mark.asyncio
async def test_get_fundamentals_symbol_is_case_insensitive(db_session: AsyncSession) -> None:
    """get_fundamentals normalises the symbol to upper-case before lookup."""
    ticker = await _seed_ticker(db_session)
    await _seed_snapshot(db_session, ticker.id)
    await db_session.commit()

    service = FundamentalsService(db_session)
    result = await service.get_fundamentals("aapl")
    assert result.symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_fundamentals_without_statements_returns_partial(
    db_session: AsyncSession,
) -> None:
    """When no annual statements exist, quality.roic and growth are None (snapshot only)."""
    ticker = await _seed_ticker(db_session)
    await _seed_snapshot(db_session, ticker.id)
    await db_session.commit()

    service = FundamentalsService(db_session)
    result = await service.get_fundamentals("AAPL")

    assert result.quality.roic is None
    assert result.quality.roe is not None  # comes from snapshot
    assert result.growth.revenue_cagr_1y is None
    # overall may still be non-None (value + partial quality)
    assert result.score.growth is None


@pytest.mark.asyncio
async def test_get_fundamentals_writes_to_cache(db_session: AsyncSession) -> None:
    """Result is written to cache after a miss."""
    ticker = await _seed_ticker(db_session)
    await _seed_snapshot(db_session, ticker.id)
    await db_session.commit()

    import app.services.fundamentals.service as svc_module

    set_json_mock: AsyncMock = svc_module.cache.set_json  # type: ignore[assignment]

    service = FundamentalsService(db_session)
    await service.get_fundamentals("AAPL")

    set_json_mock.assert_called_once()
    call_args = set_json_mock.call_args
    assert call_args.kwargs.get("ttl") == CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_fundamentals_returns_cached_result(db_session: AsyncSession) -> None:
    """On a cache hit, the result is deserialised from the cached dict."""
    ticker = await _seed_ticker(db_session)
    await _seed_snapshot(db_session, ticker.id)
    await db_session.commit()

    # First call — compute and warm cache
    service = FundamentalsService(db_session)
    live = await service.get_fundamentals("AAPL")

    # Replace get_json with a stub that returns the cached payload
    import app.services.fundamentals.service as svc_module

    cached_payload = live.to_dict()
    svc_module.cache.get_json = AsyncMock(return_value=cached_payload)  # type: ignore[assignment]
    svc_module.cache.set_json = AsyncMock()  # type: ignore[assignment]

    cached_result = await service.get_fundamentals("AAPL")
    assert cached_result.symbol == live.symbol
    assert cached_result.score.overall == live.score.overall
    # set_json must not be called again (served from cache)
    svc_module.cache.set_json.assert_not_called()
