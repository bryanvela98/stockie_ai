"""
Description: Unit tests for PriceRepository using an in-memory SQLite database.
             A Ticker row is pre-inserted via TickerRepository in each test to
             satisfy the foreign key constraint on price_bars.ticker_id.
             Covers upsert_bars (including idempotency) and get_bars (date range
             and interval filtering).
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; 6 test cases.
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import PriceBar as PriceBarDTO
from app.data_providers.models import TickerInfo
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository

# ── helpers ───────────────────────────────────────────────────────────────────

_AAPL_INFO = TickerInfo(
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
    asset_type="EQUITY",
)


def _make_bar(dt: date, close: float = 150.0) -> PriceBarDTO:
    """Return a minimal PriceBarDTO for the given date."""
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


async def _seed_ticker(session: AsyncSession) -> int:
    """Insert AAPL and return its primary key."""
    repo = TickerRepository(session)
    ticker = await repo.upsert(_AAPL_INFO)
    await session.commit()
    return ticker.id


# ── upsert_bars ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_bars_inserts_rows(db_session: AsyncSession) -> None:
    """A batch of 3 bars is persisted as 3 distinct rows."""
    ticker_id = await _seed_ticker(db_session)
    bars = [_make_bar(date(2024, 1, d)) for d in (2, 3, 4)]

    repo = PriceRepository(db_session)
    count = await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    assert count == 3
    stored = await repo.get_bars(ticker_id, date(2024, 1, 1), date(2024, 1, 31))
    assert len(stored) == 3


@pytest.mark.asyncio
async def test_upsert_bars_is_idempotent(db_session: AsyncSession) -> None:
    """Inserting the same batch twice produces no duplicate rows."""
    ticker_id = await _seed_ticker(db_session)
    bars = [_make_bar(date(2024, 1, d)) for d in (2, 3, 4)]

    repo = PriceRepository(db_session)
    await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()
    await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    stored = await repo.get_bars(ticker_id, date(2024, 1, 1), date(2024, 1, 31))
    assert len(stored) == 3


@pytest.mark.asyncio
async def test_upsert_bars_returns_count(db_session: AsyncSession) -> None:
    """upsert_bars returns the number of newly inserted rows (not updates)."""
    ticker_id = await _seed_ticker(db_session)
    bars = [_make_bar(date(2024, 1, d)) for d in (2, 3, 4)]

    repo = PriceRepository(db_session)
    inserted = await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    # All 3 are new
    assert inserted == 3

    # Re-running the same batch: 0 new inserts
    inserted_again = await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()
    assert inserted_again == 0


# ── get_bars ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bars_returns_in_date_range(db_session: AsyncSession) -> None:
    """Only bars within the requested date range are returned."""
    ticker_id = await _seed_ticker(db_session)
    # Insert bars on Jan 2, 3, 4, 5
    bars = [_make_bar(date(2024, 1, d)) for d in (2, 3, 4, 5)]

    repo = PriceRepository(db_session)
    await repo.upsert_bars(ticker_id, bars)
    await db_session.commit()

    # Query only Jan 3–4
    result = await repo.get_bars(ticker_id, date(2024, 1, 3), date(2024, 1, 4))
    assert len(result) == 2
    timestamps = [r.timestamp.date() for r in result]
    assert date(2024, 1, 3) in timestamps
    assert date(2024, 1, 4) in timestamps
    assert date(2024, 1, 2) not in timestamps
    assert date(2024, 1, 5) not in timestamps


@pytest.mark.asyncio
async def test_get_bars_filters_by_interval(db_session: AsyncSession) -> None:
    """Bars with a different interval are excluded from results."""
    ticker_id = await _seed_ticker(db_session)

    repo = PriceRepository(db_session)
    daily = [_make_bar(date(2024, 1, 2))]
    hourly = [_make_bar(date(2024, 1, 2), close=149.0)]

    await repo.upsert_bars(ticker_id, daily, interval="1d")
    await repo.upsert_bars(ticker_id, hourly, interval="1h")
    await db_session.commit()

    daily_results = await repo.get_bars(
        ticker_id, date(2024, 1, 1), date(2024, 1, 31), interval="1d"
    )
    hourly_results = await repo.get_bars(
        ticker_id, date(2024, 1, 1), date(2024, 1, 31), interval="1h"
    )

    assert len(daily_results) == 1
    assert len(hourly_results) == 1
    assert float(daily_results[0].close) == pytest.approx(150.0)
    assert float(hourly_results[0].close) == pytest.approx(149.0)


@pytest.mark.asyncio
async def test_get_bars_empty_when_no_data(db_session: AsyncSession) -> None:
    """An empty result set returns [] with no error."""
    ticker_id = await _seed_ticker(db_session)
    repo = PriceRepository(db_session)

    result = await repo.get_bars(ticker_id, date(2024, 1, 1), date(2024, 1, 31))
    assert result == []
