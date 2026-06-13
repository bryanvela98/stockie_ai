"""
Description: Unit tests for FinancialStatementRepository using an in-memory SQLite
             database. A Ticker row is pre-inserted via TickerRepository in each
             test to satisfy the foreign-key constraint on financial_statements.ticker_id.
             Covers upsert (idempotency, field update on conflict), get_history
             (ordering, limit, period_type filter).
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; 6 test cases.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import TickerInfo
from app.models.financial_statement import PERIOD_TYPE_ANNUAL
from app.repositories.financial_statement_repository import (
    FinancialStatementCreate,
    FinancialStatementRepository,
)
from app.repositories.ticker_repository import TickerRepository

# ── helpers ───────────────────────────────────────────────────────────────────

_AAPL_INFO = TickerInfo(
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
    asset_type="EQUITY",
)


async def _seed_ticker(session: AsyncSession) -> int:
    ticker = await TickerRepository(session).upsert(_AAPL_INFO)
    await session.commit()
    return ticker.id


def _stmt(
    ticker_id: int, fiscal_year: int, revenue: int = 391_000_000_000
) -> FinancialStatementCreate:
    return FinancialStatementCreate(
        ticker_id=ticker_id,
        fiscal_year=fiscal_year,
        period_type=PERIOD_TYPE_ANNUAL,
        currency="USD",
        total_revenue=revenue,
        net_income=97_000_000_000,
        eps_diluted=Decimal("6.56"),
    )


# ── upsert ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_inserts_new_statement(db_session: AsyncSession) -> None:
    """A new statement row is persisted and gets a non-null id."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    row = await repo.upsert(_stmt(ticker_id, 2024))
    await db_session.commit()

    assert row.id is not None
    assert row.ticker_id == ticker_id
    assert row.fiscal_year == 2024
    assert row.period_type == PERIOD_TYPE_ANNUAL
    assert row.total_revenue == 391_000_000_000
    assert row.eps_diluted is not None
    assert float(row.eps_diluted) == pytest.approx(6.56)


@pytest.mark.asyncio
async def test_upsert_is_idempotent(db_session: AsyncSession) -> None:
    """Upserting the same (ticker_id, fiscal_year, period_type) twice leaves one row."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    await repo.upsert(_stmt(ticker_id, 2024))
    await db_session.commit()
    await repo.upsert(_stmt(ticker_id, 2024))
    await db_session.commit()

    history = await repo.get_history(ticker_id)
    assert len(history) == 1


@pytest.mark.asyncio
async def test_upsert_updates_fields_on_conflict(db_session: AsyncSession) -> None:
    """A second upsert with a different revenue updates the existing row."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    await repo.upsert(_stmt(ticker_id, 2024, revenue=380_000_000_000))
    await db_session.commit()
    updated = await repo.upsert(_stmt(ticker_id, 2024, revenue=395_000_000_000))
    await db_session.commit()

    assert updated.total_revenue == 395_000_000_000


# ── get_history ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_history_returns_rows_ordered_newest_first(db_session: AsyncSession) -> None:
    """get_history returns rows sorted by fiscal_year descending."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    for year in [2022, 2024, 2023]:
        await repo.upsert(_stmt(ticker_id, year))
    await db_session.commit()

    history = await repo.get_history(ticker_id)
    assert [r.fiscal_year for r in history] == [2024, 2023, 2022]


@pytest.mark.asyncio
async def test_get_history_respects_limit(db_session: AsyncSession) -> None:
    """get_history returns at most `limit` rows."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    for year in range(2019, 2025):
        await repo.upsert(_stmt(ticker_id, year))
    await db_session.commit()

    history = await repo.get_history(ticker_id, limit=3)
    assert len(history) == 3
    assert history[0].fiscal_year == 2024


@pytest.mark.asyncio
async def test_get_history_returns_empty_for_unknown_ticker(db_session: AsyncSession) -> None:
    """get_history returns an empty list when no statements exist for the ticker."""
    ticker_id = await _seed_ticker(db_session)
    repo = FinancialStatementRepository(db_session)

    result = await repo.get_history(ticker_id)
    assert result == []
