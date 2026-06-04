"""
Description: Endpoint tests for GET /tickers/search and GET /tickers/{symbol}.
             Uses an in-memory SQLite database via FastAPI dependency override so
             no live PostgreSQL connection is required.  Three tickers are seeded
             (AAPL, MSFT, SPY) before each test via TickerRepository.upsert().
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; 8 test cases for search and detail endpoints.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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
from app.repositories.ticker_repository import TickerRepository

# ── seed data ─────────────────────────────────────────────────────────────────

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

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_client() -> AsyncIterator[AsyncClient]:
    """AsyncClient with get_db overridden to an in-memory SQLite session.

    Creates the schema, seeds AAPL / MSFT / SPY, then yields a configured
    AsyncClient.  Clears dependency overrides and disposes the engine on teardown.

    Yields:
        An AsyncClient pointed at the in-process ASGI app with a real SQLite DB.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed tickers
    async with session_factory() as session:
        repo = TickerRepository(session)
        for info in (_AAPL, _MSFT, _SPY):
            await repo.upsert(info)
        await session.commit()

    # Override get_db
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


# ── /tickers/search tests ─────────────────────────────────────────────────────


async def test_search_returns_results(seeded_client: AsyncClient) -> None:
    """A matching prefix returns results with the expected shape."""
    response = await seeded_client.get("/tickers/search?q=AA")
    assert response.status_code == 200
    body = response.json()
    assert "results" in body and "total" in body
    symbols = [r["symbol"] for r in body["results"]]
    assert "AAPL" in symbols


async def test_search_case_insensitive(seeded_client: AsyncClient) -> None:
    """Lowercase query matches uppercase symbol."""
    response = await seeded_client.get("/tickers/search?q=aapl")
    assert response.status_code == 200
    symbols = [r["symbol"] for r in response.json()["results"]]
    assert "AAPL" in symbols


async def test_search_empty_for_no_match(seeded_client: AsyncClient) -> None:
    """A query that matches nothing returns an empty results list (not 404)."""
    response = await seeded_client.get("/tickers/search?q=ZZZNOTEXIST")
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["total"] == 0


async def test_search_missing_q_returns_422(seeded_client: AsyncClient) -> None:
    """Omitting the required `q` parameter returns a 422 validation error."""
    response = await seeded_client.get("/tickers/search")
    assert response.status_code == 422


async def test_search_limit_respected(seeded_client: AsyncClient) -> None:
    """limit=1 returns at most one result."""
    response = await seeded_client.get("/tickers/search?q=A&limit=1")
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 1


# ── /tickers/{symbol} tests ───────────────────────────────────────────────────


async def test_get_ticker_returns_200(seeded_client: AsyncClient) -> None:
    """An exact symbol match returns the ticker with the correct fields."""
    response = await seeded_client.get("/tickers/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["exchange"] == "NASDAQ"
    assert body["asset_type"] == "EQUITY"


async def test_get_ticker_case_insensitive(seeded_client: AsyncClient) -> None:
    """Lowercase symbol path returns the same ticker."""
    response = await seeded_client.get("/tickers/aapl")
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


async def test_get_ticker_404_for_unknown(seeded_client: AsyncClient) -> None:
    """A symbol that was never inserted returns 404."""
    response = await seeded_client.get("/tickers/DOESNOTEXIST")
    assert response.status_code == 404
