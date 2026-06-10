"""
Description: Unit tests for CorporateActionRepository using an in-memory SQLite database.
             A Ticker row is pre-inserted via TickerRepository in each test to
             satisfy the foreign key constraint on corporate_actions.ticker_id.
             Covers upsert (idempotency, ratio update), and get_by_ticker
             (unfiltered and with a `since` date filter).
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; 5 test cases (Sprint 2-B Task 2).
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import TickerInfo
from app.repositories.corporate_action_repository import (
    ACTION_TYPE_DIVIDEND,
    ACTION_TYPE_SPLIT,
    CorporateActionCreate,
    CorporateActionRepository,
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
    """Insert AAPL and return its primary key."""
    ticker = await TickerRepository(session).upsert(_AAPL_INFO)
    await session.commit()
    return ticker.id


def _split(ticker_id: int, ex_date: date, ratio: float = 2.0) -> CorporateActionCreate:
    return CorporateActionCreate(
        ticker_id=ticker_id,
        action_type=ACTION_TYPE_SPLIT,
        ex_date=ex_date,
        ratio=Decimal(str(ratio)),
    )


def _dividend(ticker_id: int, ex_date: date, amount: float = 0.25) -> CorporateActionCreate:
    return CorporateActionCreate(
        ticker_id=ticker_id,
        action_type=ACTION_TYPE_DIVIDEND,
        ex_date=ex_date,
        ratio=Decimal(str(amount)),
    )


# ── upsert ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_inserts_new_action(db_session: AsyncSession) -> None:
    """A new corporate action is persisted and gets a non-null id."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)

    action = await repo.upsert(_split(ticker_id, date(2024, 6, 10)))
    await db_session.commit()

    assert action.id is not None
    assert action.ticker_id == ticker_id
    assert action.action_type == ACTION_TYPE_SPLIT
    assert action.ex_date == date(2024, 6, 10)
    assert action.ratio == Decimal("2.0")


@pytest.mark.asyncio
async def test_upsert_is_idempotent(db_session: AsyncSession) -> None:
    """Upserting the same (ticker_id, action_type, ex_date) twice leaves one row."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)

    await repo.upsert(_split(ticker_id, date(2024, 6, 10)))
    await db_session.commit()
    await repo.upsert(_split(ticker_id, date(2024, 6, 10)))
    await db_session.commit()

    rows = await repo.get_by_ticker(ticker_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_upsert_updates_ratio_on_conflict(db_session: AsyncSession) -> None:
    """A second upsert with a different ratio updates the existing row's ratio."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)

    await repo.upsert(_split(ticker_id, date(2024, 6, 10), ratio=2.0))
    await db_session.commit()
    updated = await repo.upsert(_split(ticker_id, date(2024, 6, 10), ratio=3.0))
    await db_session.commit()

    assert float(updated.ratio) == pytest.approx(3.0)
    rows = await repo.get_by_ticker(ticker_id)
    assert len(rows) == 1
    assert float(rows[0].ratio) == pytest.approx(3.0)


# ── get_by_ticker ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_ticker_returns_all_actions(db_session: AsyncSession) -> None:
    """All actions for the ticker are returned when no since filter is given."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)

    await repo.upsert(_split(ticker_id, date(2023, 1, 15)))
    await repo.upsert(_dividend(ticker_id, date(2023, 3, 20)))
    await repo.upsert(_split(ticker_id, date(2024, 6, 10)))
    await db_session.commit()

    rows = await repo.get_by_ticker(ticker_id)
    assert len(rows) == 3
    # Ordered by ex_date ascending
    assert rows[0].ex_date == date(2023, 1, 15)
    assert rows[1].ex_date == date(2023, 3, 20)
    assert rows[2].ex_date == date(2024, 6, 10)


@pytest.mark.asyncio
async def test_get_by_ticker_filters_by_since(db_session: AsyncSession) -> None:
    """Only actions with ex_date >= since are returned."""
    ticker_id = await _seed_ticker(db_session)
    repo = CorporateActionRepository(db_session)

    await repo.upsert(_split(ticker_id, date(2023, 1, 15)))
    await repo.upsert(_dividend(ticker_id, date(2023, 3, 20)))
    await repo.upsert(_split(ticker_id, date(2024, 6, 10)))
    await db_session.commit()

    rows = await repo.get_by_ticker(ticker_id, since=date(2023, 3, 20))
    assert len(rows) == 2
    assert rows[0].ex_date == date(2023, 3, 20)
    assert rows[1].ex_date == date(2024, 6, 10)
