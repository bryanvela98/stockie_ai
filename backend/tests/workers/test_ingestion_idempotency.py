"""
Description: Idempotency tests for the ingestion layer using in-memory SQLite.
             Verifies that running upsert_bars and FundamentalsRepository.upsert
             twice with identical data produces no duplicate rows.
             Uses the same async SQLite fixtures as the repository tests so no
             live PostgreSQL connection is required.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; 2 idempotency test scenarios (Sprint 2-B Task 9).
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import PriceBar as PriceBarDTO
from app.data_providers.models import TickerInfo
from app.models.fundamentals import Fundamentals
from app.models.price_bar import PriceBar as PriceBarModel
from app.repositories.fundamentals_repository import FundamentalsCreate, FundamentalsRepository
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository

# ── helpers ───────────────────────────────────────────────────────────────────

_AAPL_INFO = TickerInfo(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ", asset_type="EQUITY")


async def _seed_ticker(session: AsyncSession) -> int:
    ticker = await TickerRepository(session).upsert(_AAPL_INFO)
    await session.commit()
    return ticker.id


def _make_bar(dt: date, close: float = 150.0) -> PriceBarDTO:
    return PriceBarDTO(
        symbol="AAPL",
        timestamp=datetime(dt.year, dt.month, dt.day, 21, 0, 0, tzinfo=UTC),
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=10_000_000,
        adjusted_close=close,
    )


# ── daily prices idempotency ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_bars_twice_produces_no_duplicates(db_session: AsyncSession) -> None:
    """Calling upsert_bars twice with identical data leaves exactly N rows."""
    ticker_id = await _seed_ticker(db_session)
    bars = [_make_bar(date(2024, 1, d)) for d in (2, 3, 4, 5)]
    repo = PriceRepository(db_session)

    first_count = await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    second_count = await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    result = await db_session.execute(
        select(PriceBarModel).where(PriceBarModel.ticker_id == ticker_id)
    )
    stored = result.scalars().all()

    assert first_count == 4
    assert second_count == 0  # no new rows on re-run
    assert len(stored) == 4


# ── fundamentals idempotency ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fundamentals_upsert_twice_produces_one_row(db_session: AsyncSession) -> None:
    """Calling FundamentalsRepository.upsert twice for the same (ticker_id, as_of)
    leaves exactly one row in the fundamentals table."""
    ticker_id = await _seed_ticker(db_session)
    repo = FundamentalsRepository(db_session)
    snapshot = FundamentalsCreate(
        ticker_id=ticker_id,
        as_of=date(2024, 3, 31),
        pe_ratio=Decimal("28.5"),
        market_cap=3_000_000_000_000,
    )

    await repo.upsert(snapshot)
    await db_session.commit()
    await repo.upsert(snapshot)
    await db_session.commit()

    result = await db_session.execute(
        select(Fundamentals).where(Fundamentals.ticker_id == ticker_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
