"""
Description: Endpoint tests for GET /tickers/{symbol}/prices.
             Uses an in-memory SQLite database via FastAPI dependency override so
             no live PostgreSQL connection is required. AAPL is seeded with a small
             set of price bars to exercise pagination, filtering, and error paths.
Last Modified By: bvela
Created: 2026-06-11
Last Modified:
    2026-06-11 - File created; 8 test cases for the prices endpoint.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import models as _models  # noqa: F401 — registers all ORM models on Base.metadata
from app.core.db import get_db
from app.data_providers.models import TickerInfo
from app.main import app
from app.models.base import Base
from app.models.price_bar import PriceBar as PriceBarModel
from app.repositories.ticker_repository import TickerRepository

# ── seed helpers ──────────────────────────────────────────────────────────────

_AAPL = TickerInfo(
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
    asset_type="EQUITY",
    currency="USD",
)


def _bar(ticker_id: int, ts: datetime, close: float = 100.0) -> PriceBarModel:
    """Build a minimal PriceBar ORM row for test seeding."""
    return PriceBarModel(
        ticker_id=ticker_id,
        timestamp=ts,
        interval="1d",
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=1_000_000,
        adjusted_close=Decimal(str(close)),
    )


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def price_client() -> AsyncIterator[AsyncClient]:
    """AsyncClient backed by SQLite with AAPL seeded and 5 daily price bars.

    Bars are on 2025-01-02, 2025-01-03, 2025-01-06, 2025-01-07, 2025-01-08.

    Yields:
        An AsyncClient pointed at the in-process ASGI app.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        repo = TickerRepository(session)
        ticker = await repo.upsert(_AAPL)
        await session.flush()

        bar_dates = [
            datetime(2025, 1, 2, tzinfo=UTC),
            datetime(2025, 1, 3, tzinfo=UTC),
            datetime(2025, 1, 6, tzinfo=UTC),
            datetime(2025, 1, 7, tzinfo=UTC),
            datetime(2025, 1, 8, tzinfo=UTC),
        ]
        for ts in bar_dates:
            session.add(_bar(ticker.id, ts, close=float(ts.day) * 10))

        await session.commit()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


# ── tests ─────────────────────────────────────────────────────────────────────


async def test_prices_returns_200_with_bars(price_client: AsyncClient) -> None:
    """A valid request for a seeded ticker returns 200 with a non-empty bars list."""
    response = await price_client.get(
        "/tickers/AAPL/prices", params={"from": "2025-01-01", "to": "2025-01-31"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["timeframe"] == "1d"
    assert isinstance(body["bars"], list)
    assert len(body["bars"]) == 5
    # Each bar has the expected compact fields
    bar = body["bars"][0]
    assert {"t", "o", "h", "low", "c", "v"}.issubset(bar.keys())


async def test_prices_empty_bars_when_no_data_in_range(price_client: AsyncClient) -> None:
    """A valid symbol with no bars in the requested range returns 200 with empty bars."""
    response = await price_client.get(
        "/tickers/AAPL/prices", params={"from": "2024-01-01", "to": "2024-12-31"}
    )
    assert response.status_code == 200
    assert response.json()["bars"] == []
    assert response.json()["next_cursor"] is None


async def test_prices_404_for_unknown_symbol(price_client: AsyncClient) -> None:
    """A symbol that was never inserted returns 404."""
    response = await price_client.get(
        "/tickers/ZZZZ/prices", params={"from": "2025-01-01", "to": "2025-01-31"}
    )
    assert response.status_code == 404


async def test_prices_400_from_after_to(price_client: AsyncClient) -> None:
    """from > to returns 400."""
    response = await price_client.get(
        "/tickers/AAPL/prices", params={"from": "2025-06-01", "to": "2025-01-01"}
    )
    assert response.status_code == 400


async def test_prices_400_invalid_timeframe(price_client: AsyncClient) -> None:
    """An unrecognised timeframe string returns 400."""
    response = await price_client.get(
        "/tickers/AAPL/prices",
        params={"from": "2025-01-01", "to": "2025-01-31", "timeframe": "4h"},
    )
    assert response.status_code == 400


async def test_prices_pagination_next_cursor_set(price_client: AsyncClient) -> None:
    """When limit is smaller than available bars, next_cursor is populated."""
    response = await price_client.get(
        "/tickers/AAPL/prices",
        params={"from": "2025-01-01", "to": "2025-01-31", "limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["bars"]) == 2
    assert body["next_cursor"] is not None


async def test_prices_cursor_advances_page(price_client: AsyncClient) -> None:
    """Using next_cursor from page 1 returns the next set of bars without overlap."""
    page1 = await price_client.get(
        "/tickers/AAPL/prices",
        params={"from": "2025-01-01", "to": "2025-01-31", "limit": 2},
    )
    cursor = page1.json()["next_cursor"]
    first_page_ts = {b["t"] for b in page1.json()["bars"]}

    page2 = await price_client.get(
        "/tickers/AAPL/prices",
        params={"from": "2025-01-01", "to": "2025-01-31", "limit": 2, "cursor": cursor},
    )
    assert page2.status_code == 200
    second_page_ts = {b["t"] for b in page2.json()["bars"]}
    # No timestamp appears on both pages
    assert first_page_ts.isdisjoint(second_page_ts)


async def test_prices_data_as_of_present(price_client: AsyncClient) -> None:
    """data_as_of is present in the response when price bars exist."""
    response = await price_client.get(
        "/tickers/AAPL/prices", params={"from": "2025-01-01", "to": "2025-01-31"}
    )
    body = response.json()
    assert "data_as_of" in body
    # data_as_of should be a parseable ISO datetime string
    datetime.fromisoformat(body["data_as_of"])
