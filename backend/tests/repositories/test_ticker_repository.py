"""
Description: Unit tests for TickerRepository using an in-memory SQLite database.
             Covers all four public methods: get_by_symbol, get_by_id, upsert,
             and search. No live PostgreSQL connection is required.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; 10 test cases.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import TickerInfo
from app.models.ticker import Ticker
from app.repositories.ticker_repository import TickerRepository

# ── helpers ───────────────────────────────────────────────────────────────────

_AAPL = TickerInfo(
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
    asset_type="EQUITY",
    currency="USD",
    sector="Technology",
    industry="Consumer Electronics",
)

_MSFT = TickerInfo(
    symbol="MSFT",
    name="Microsoft Corporation",
    exchange="NASDAQ",
    asset_type="EQUITY",
    currency="USD",
    sector="Technology",
    industry="Software—Infrastructure",
)

_SPY = TickerInfo(
    symbol="SPY",
    name="SPDR S&P 500 ETF Trust",
    exchange="NYSE",
    asset_type="ETF",
    currency="USD",
)


# ── upsert ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_creates_new_ticker(db_session: AsyncSession) -> None:
    """Upserting into an empty table inserts a new row."""
    repo = TickerRepository(db_session)
    ticker = await repo.upsert(_AAPL)
    await db_session.commit()

    assert isinstance(ticker, Ticker)
    assert ticker.id is not None
    assert ticker.symbol == "AAPL"
    assert ticker.name == "Apple Inc."
    assert ticker.sector == "Technology"


@pytest.mark.asyncio
async def test_upsert_is_idempotent(db_session: AsyncSession) -> None:
    """Calling upsert twice with the same symbol does not create a duplicate."""
    repo = TickerRepository(db_session)
    first = await repo.upsert(_AAPL)
    await db_session.commit()
    second = await repo.upsert(_AAPL)
    await db_session.commit()

    assert first.id == second.id

    # Confirm only one row exists
    all_tickers = await repo.search("AAPL")
    assert len(all_tickers) == 1


@pytest.mark.asyncio
async def test_upsert_updates_mutable_fields(db_session: AsyncSession) -> None:
    """A second upsert with an updated name should persist the new value."""
    repo = TickerRepository(db_session)
    await repo.upsert(_AAPL)
    await db_session.commit()

    updated = TickerInfo(
        symbol="AAPL",
        name="Apple Inc. (Updated)",
        exchange="NASDAQ",
        asset_type="EQUITY",
        currency="USD",
    )
    await repo.upsert(updated)
    await db_session.commit()

    fetched = await repo.get_by_symbol("AAPL")
    assert fetched is not None
    assert fetched.name == "Apple Inc. (Updated)"


# ── get_by_symbol ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_symbol_returns_ticker(db_session: AsyncSession) -> None:
    """An exact symbol match (case-insensitive) returns the row."""
    repo = TickerRepository(db_session)
    await repo.upsert(_AAPL)
    await db_session.commit()

    result = await repo.get_by_symbol("aapl")  # lowercase input
    assert result is not None
    assert result.symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_by_symbol_returns_none_for_missing(db_session: AsyncSession) -> None:
    """An unknown symbol returns None."""
    repo = TickerRepository(db_session)
    result = await repo.get_by_symbol("DOESNOTEXIST")
    assert result is None


# ── get_by_id ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_id_returns_ticker(db_session: AsyncSession) -> None:
    """Fetching by primary key returns the correct row."""
    repo = TickerRepository(db_session)
    inserted = await repo.upsert(_AAPL)
    await db_session.commit()

    result = await repo.get_by_id(inserted.id)
    assert result is not None
    assert result.symbol == "AAPL"


# ── search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_prefix_match_on_symbol(db_session: AsyncSession) -> None:
    """A partial symbol prefix returns matching tickers."""
    repo = TickerRepository(db_session)
    for info in (_AAPL, _MSFT, _SPY):
        await repo.upsert(info)
    await db_session.commit()

    results = await repo.search("AA")
    symbols = [t.symbol for t in results]
    assert "AAPL" in symbols
    assert "MSFT" not in symbols


@pytest.mark.asyncio
async def test_search_prefix_match_on_name(db_session: AsyncSession) -> None:
    """A name prefix returns matching tickers."""
    repo = TickerRepository(db_session)
    for info in (_AAPL, _MSFT, _SPY):
        await repo.upsert(info)
    await db_session.commit()

    results = await repo.search("apple")
    symbols = [t.symbol for t in results]
    assert "AAPL" in symbols


@pytest.mark.asyncio
async def test_search_is_case_insensitive(db_session: AsyncSession) -> None:
    """Search is case-insensitive for both symbol and name."""
    repo = TickerRepository(db_session)
    await repo.upsert(_AAPL)
    await db_session.commit()

    results = await repo.search("aapl")
    assert any(t.symbol == "AAPL" for t in results)


@pytest.mark.asyncio
async def test_search_respects_limit(db_session: AsyncSession) -> None:
    """limit=1 returns at most one result even when more match."""
    repo = TickerRepository(db_session)
    for info in (_AAPL, _MSFT, _SPY):
        await repo.upsert(info)
    await db_session.commit()

    # All three have "EQUITY" or "ETF" but all contain letter combinations;
    # use a broad prefix that matches multiple tickers
    results = await repo.search("a", limit=1)
    assert len(results) <= 1
