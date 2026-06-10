"""
Description: Tests for the split-adjusted close recomputation logic used in the
             corporate_actions_sync Celery task.
             Verifies that a 2-for-1 split halves adjusted_close for all
             price_bars rows before the ex_date, and that inserting the same split
             twice only produces one corporate_actions row (idempotency).
             Uses in-memory SQLite fixtures — no live DB or Celery worker required.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; 2 split-adjustment scenarios (Sprint 2-B Task 9).
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import PriceBar as PriceBarDTO
from app.data_providers.models import TickerInfo
from app.models.corporate_action import CorporateAction
from app.models.price_bar import PriceBar as PriceBarModel
from app.repositories.corporate_action_repository import (
    ACTION_TYPE_SPLIT,
    CorporateActionCreate,
    CorporateActionRepository,
)
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository
from app.workers.tasks.corporate_actions_sync import _recompute_adjusted_close

# ── helpers ───────────────────────────────────────────────────────────────────

_AAPL_INFO = TickerInfo(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ", asset_type="EQUITY")


async def _seed_ticker(session: AsyncSession) -> int:
    ticker = await TickerRepository(session).upsert(_AAPL_INFO)
    await session.commit()
    return ticker.id


def _make_bar(dt: date, close: float = 200.0) -> PriceBarDTO:
    return PriceBarDTO(
        symbol="AAPL",
        timestamp=datetime(dt.year, dt.month, dt.day, 21, 0, 0, tzinfo=UTC),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
        adjusted_close=close,
    )


# ── split-adjustment correctness ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_split_halves_adjusted_close_for_pre_split_bars(db_session: AsyncSession) -> None:
    """A 2-for-1 split on 2024-06-10 must halve adjusted_close for all bars
    with timestamp < 2024-06-10 00:00 UTC."""
    ticker_id = await _seed_ticker(db_session)
    price_repo = PriceRepository(db_session)

    # Insert 5 bars before the split date and 2 bars on/after it
    pre_split_dates = [date(2024, 6, d) for d in (3, 4, 5, 6, 7)]
    post_split_dates = [date(2024, 6, d) for d in (10, 11)]
    all_bars = [_make_bar(d) for d in pre_split_dates + post_split_dates]

    await price_repo.upsert_bars(ticker_id, all_bars)
    await db_session.commit()

    # Run the recomputation for a 2-for-1 split on 2024-06-10
    ex_date_utc = datetime(2024, 6, 10, tzinfo=UTC)
    split_ratio = Decimal("2.0")
    rows_updated = await _recompute_adjusted_close(db_session, ticker_id, ex_date_utc, split_ratio)
    await db_session.commit()

    # Only the 5 pre-split bars should be updated
    assert rows_updated == 5

    result = await db_session.execute(
        select(PriceBarModel)
        .where(PriceBarModel.ticker_id == ticker_id)
        .order_by(PriceBarModel.timestamp)
    )
    bars = result.scalars().all()
    assert len(bars) == 7

    for bar in bars:
        # SQLite returns naive datetimes — normalise before comparing to UTC-aware
        bar_ts = bar.timestamp if bar.timestamp.tzinfo else bar.timestamp.replace(tzinfo=UTC)
        if bar_ts < ex_date_utc:
            # adjusted_close should be close / 2
            assert bar.adjusted_close is not None
            assert float(bar.adjusted_close) == pytest.approx(float(bar.close) / 2.0)
        else:
            # post-split bars untouched: adjusted_close == close (200.0)
            assert bar.adjusted_close is not None
            assert float(bar.adjusted_close) == pytest.approx(float(bar.close))


# ── corporate action idempotency ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_split_inserted_twice_leaves_one_row(db_session: AsyncSession) -> None:
    """Inserting the same split corporate action twice produces exactly one row."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)
    split = CorporateActionCreate(
        ticker_id=ticker_id,
        action_type=ACTION_TYPE_SPLIT,
        ex_date=date(2024, 6, 10),
        ratio=Decimal("2.0"),
    )

    await repo.upsert(split)
    await db_session.commit()
    await repo.upsert(split)
    await db_session.commit()

    result = await db_session.execute(
        select(CorporateAction).where(CorporateAction.ticker_id == ticker_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].action_type == ACTION_TYPE_SPLIT
    assert rows[0].ex_date == date(2024, 6, 10)
