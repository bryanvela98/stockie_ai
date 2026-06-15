"""
Description: HTTP integration tests for the three fundamentals endpoints:
               GET /tickers/{symbol}/fundamentals
               GET /tickers/{symbol}/dcf
               GET /tickers/{symbol}/peers
             Uses an in-memory SQLite engine (via db_session fixture), overrides
             the get_db dependency, and patches Redis cache helpers so no live
             infrastructure is needed.
Last Modified By: bvela
Created: 2026-06-15
Last Modified:
    2026-06-15 - File created; shape, 404, and 400 tests for all three endpoints.
"""

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.data_providers.models import TickerInfo
from app.main import app
from app.repositories.financial_statement_repository import (
    FinancialStatementCreate,
    FinancialStatementRepository,
)
from app.repositories.fundamentals_repository import FundamentalsCreate, FundamentalsRepository
from app.repositories.ticker_repository import TickerRepository

# ── Seed helpers ──────────────────────────────────────────────────────────────


async def _seed_aapl(session: AsyncSession) -> None:
    """Insert AAPL ticker, snapshot, and one annual statement."""
    ticker_repo = TickerRepository(session)
    ticker = await ticker_repo.upsert(
        TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_type="equity",
            currency="USD",
            sector="Technology",
        )
    )
    fund_repo = FundamentalsRepository(session)
    await fund_repo.upsert(
        FundamentalsCreate(
            ticker_id=ticker.id,
            as_of=date(2024, 1, 1),
            market_cap=3_000_000_000_000,
            pe_ratio=Decimal("30.0"),
            pb_ratio=Decimal("45.0"),
            roe=Decimal("1.47"),
            debt_to_equity=Decimal("2.18"),
        )
    )
    stmt_repo = FinancialStatementRepository(session)
    await stmt_repo.upsert(
        FinancialStatementCreate(
            ticker_id=ticker.id,
            fiscal_year=2024,
            operating_cash_flow=118_254_000_000,
            capital_expenditure=-9_447_000_000,
            total_debt=96_630_000_000,
            cash_and_equivalents=65_170_000_000,
            shares_diluted=15_408_000_000,
        )
    )
    await session.commit()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def plain_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient pointing at an empty in-memory DB with get_db overridden."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with AAPL data seeded, get_db + cache helpers overridden."""
    await _seed_aapl(db_session)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch("app.core.cache.get_json", new=AsyncMock(return_value=None)),
        patch("app.core.cache.set_json", new=AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


# ── /fundamentals tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fundamentals_200_shape(seeded_client: AsyncClient) -> None:
    """GET /fundamentals returns 200 with all required top-level keys."""
    response = await seeded_client.get("/tickers/AAPL/fundamentals")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert "data_as_of" in body
    assert "ratios" in body
    assert "quality" in body
    assert "growth" in body
    assert "scores" in body


@pytest.mark.asyncio
async def test_fundamentals_scores_block(seeded_client: AsyncClient) -> None:
    """Scores block contains overall and weights_version."""
    response = await seeded_client.get("/tickers/AAPL/fundamentals")
    assert response.status_code == 200
    scores = response.json()["scores"]
    assert "overall" in scores
    assert "weights_version" in scores
    assert isinstance(scores["weights_version"], str)


@pytest.mark.asyncio
async def test_fundamentals_404_unknown_ticker(plain_client: AsyncClient) -> None:
    """GET /fundamentals for an unknown symbol returns 404."""
    with (
        patch("app.core.cache.get_json", new=AsyncMock(return_value=None)),
        patch("app.core.cache.set_json", new=AsyncMock()),
    ):
        response = await plain_client.get("/tickers/ZZZZZ/fundamentals")
    assert response.status_code == 404


# ── /dcf tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dcf_200_default_params(seeded_client: AsyncClient) -> None:
    """GET /dcf with default params returns 200 with 5-year projection."""
    response = await seeded_client.get("/tickers/AAPL/dcf")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert len(body["yearly_fcf"]) == 5
    assert body["assumptions"]["growth_rate"] == pytest.approx(0.08)
    assert body["assumptions"]["discount_rate"] == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_dcf_200_custom_years(seeded_client: AsyncClient) -> None:
    """GET /dcf?years=10 returns a 10-element yearly_fcf list."""
    response = await seeded_client.get("/tickers/AAPL/dcf?years=10")
    assert response.status_code == 200
    assert len(response.json()["yearly_fcf"]) == 10


@pytest.mark.asyncio
async def test_dcf_400_when_terminal_ge_discount(seeded_client: AsyncClient) -> None:
    """GET /dcf returns 400 when terminal_growth >= discount_rate."""
    response = await seeded_client.get("/tickers/AAPL/dcf?terminal_growth=0.10&discount_rate=0.10")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_dcf_404_unknown_ticker(plain_client: AsyncClient) -> None:
    """GET /dcf for an unknown symbol returns 404."""
    response = await plain_client.get("/tickers/ZZZZZ/dcf")
    assert response.status_code == 404


# ── /peers tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_peers_200_shape(seeded_client: AsyncClient) -> None:
    """GET /peers returns 200 with symbol and peers list."""
    response = await seeded_client.get("/tickers/AAPL/peers")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert isinstance(body["peers"], list)


@pytest.mark.asyncio
async def test_peers_200_empty_when_no_sector(db_session: AsyncSession) -> None:
    """GET /peers returns 200 with empty peers list when ticker has no sector."""
    repo = TickerRepository(db_session)
    await repo.upsert(
        TickerInfo(
            symbol="ETF1",
            name="My ETF",
            exchange="NYSE",
            asset_type="etf",
            currency="USD",
            sector=None,
        )
    )
    await db_session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/tickers/ETF1/peers")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["peers"] == []


@pytest.mark.asyncio
async def test_peers_404_unknown_ticker(plain_client: AsyncClient) -> None:
    """GET /peers for an unknown symbol returns 404."""
    response = await plain_client.get("/tickers/ZZZZZ/peers")
    assert response.status_code == 404
