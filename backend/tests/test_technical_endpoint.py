"""
Description: HTTP integration tests for the two technical endpoints:
               GET /tickers/{symbol}/indicators
               GET /tickers/{symbol}/technical
             Uses an in-memory SQLite engine (via db_session fixture), overrides
             the get_db dependency, and patches Redis cache helpers so no live
             infrastructure is needed.
Last Modified By: bvela
Created: 2026-06-18
Last Modified:
    2026-06-18 - File created; shape, 404, and param tests for both endpoints (Sprint 4-B2/B3).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.data_providers.models import PriceBar as PriceBarDTO
from app.data_providers.models import TickerInfo
from app.main import app
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository
from tests.fixtures.synthetic_series import SyntheticBar, uptrend_series

# ── Seed helpers ──────────────────────────────────────────────────────────────


async def _seed_ticker(session: AsyncSession, symbol: str = "TECH") -> int:
    repo = TickerRepository(session)
    ticker = await repo.upsert(
        TickerInfo(
            symbol=symbol,
            name=f"{symbol} Corp",
            exchange="NASDAQ",
            asset_type="equity",
            currency="USD",
            sector="Technology",
            industry="Software",
        )
    )
    return ticker.id


def _bar_to_dto(bar: SyntheticBar, symbol: str = "TECH") -> PriceBarDTO:
    return PriceBarDTO(
        symbol=symbol,
        timestamp=bar.timestamp,
        open=float(bar.open),
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        volume=bar.volume,
        adjusted_close=float(bar.adjusted_close) if bar.adjusted_close else None,
    )


async def _seed_bars(
    session: AsyncSession, ticker_id: int, bars: list[SyntheticBar], symbol: str = "TECH"
) -> None:
    repo = PriceRepository(session)
    dtos = [_bar_to_dto(b, symbol) for b in bars]
    await repo.upsert_bars(ticker_id, dtos, interval="1d")


async def _seed_tech(session: AsyncSession) -> None:
    ticker_id = await _seed_ticker(session)
    await _seed_bars(session, ticker_id, uptrend_series())
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
    """AsyncClient with TECH uptrend bars seeded and cache helpers patched."""
    await _seed_tech(db_session)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch("app.services.technical.service.cache.get_json", new=AsyncMock(return_value=None)),
        patch("app.services.technical.service.cache.set_json", new=AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


# ── /indicators tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_indicators_200_shape(seeded_client: AsyncClient) -> None:
    """GET /indicators returns 200 with expected top-level keys."""
    response = await seeded_client.get("/tickers/TECH/indicators")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "TECH"
    assert body["timeframe"] == "1d"
    assert "bar_count" in body
    assert "sma" in body
    assert "ema" in body
    assert "rsi" in body
    assert "macd" in body
    assert "bbands" in body
    assert "atr" in body


@pytest.mark.asyncio
async def test_indicators_sma_blocks(seeded_client: AsyncClient) -> None:
    """Default call returns 3 SMA blocks (20, 50, 200) with a latest value."""
    response = await seeded_client.get("/tickers/TECH/indicators")
    assert response.status_code == 200
    sma = response.json()["sma"]
    assert len(sma) == 3
    periods = [b["period"] for b in sma]
    assert 20 in periods and 50 in periods and 200 in periods
    assert all(b["latest"] is not None for b in sma)


@pytest.mark.asyncio
async def test_indicators_series_empty_by_default(seeded_client: AsyncClient) -> None:
    """Without ?series=true the series arrays are empty."""
    response = await seeded_client.get("/tickers/TECH/indicators")
    assert response.status_code == 200
    body = response.json()
    assert body["sma"][0]["series"] == []
    assert body["rsi"]["series"] == []


@pytest.mark.asyncio
async def test_indicators_series_populated_with_flag(seeded_client: AsyncClient) -> None:
    """With ?series=true the SMA series array is non-empty."""
    response = await seeded_client.get("/tickers/TECH/indicators?series=true")
    assert response.status_code == 200
    body = response.json()
    assert len(body["sma"][0]["series"]) > 0


@pytest.mark.asyncio
async def test_indicators_custom_sma_periods(seeded_client: AsyncClient) -> None:
    """?sma_periods=10,30 produces two SMA blocks with the specified periods."""
    response = await seeded_client.get("/tickers/TECH/indicators?indicators=sma&sma_periods=10,30")
    assert response.status_code == 200
    body = response.json()
    periods = [b["period"] for b in body["sma"]]
    assert periods == [10, 30]
    assert body["rsi"] is None
    assert body["macd"] is None


@pytest.mark.asyncio
async def test_indicators_subset_indicators(seeded_client: AsyncClient) -> None:
    """?indicators=rsi returns rsi populated and others None/empty."""
    response = await seeded_client.get("/tickers/TECH/indicators?indicators=rsi")
    assert response.status_code == 200
    body = response.json()
    assert body["rsi"] is not None
    assert body["sma"] == []
    assert body["macd"] is None
    assert body["bbands"] is None


@pytest.mark.asyncio
async def test_indicators_invalid_indicator_422(seeded_client: AsyncClient) -> None:
    """?indicators=xyz returns 422 with detail listing the invalid name."""
    response = await seeded_client.get("/tickers/TECH/indicators?indicators=xyz")
    assert response.status_code == 422
    assert "xyz" in response.json()["detail"]


@pytest.mark.asyncio
async def test_indicators_weekly_timeframe(seeded_client: AsyncClient) -> None:
    """?timeframe=1w resamples and returns fewer bars than daily."""
    daily = await seeded_client.get("/tickers/TECH/indicators?timeframe=1d")
    weekly = await seeded_client.get("/tickers/TECH/indicators?timeframe=1w")
    assert daily.status_code == 200
    assert weekly.status_code == 200
    assert weekly.json()["bar_count"] < daily.json()["bar_count"]


@pytest.mark.asyncio
async def test_indicators_404_unknown_ticker(plain_client: AsyncClient) -> None:
    """GET /indicators for an unknown symbol returns 404."""
    with (
        patch("app.services.technical.service.cache.get_json", new=AsyncMock(return_value=None)),
        patch("app.services.technical.service.cache.set_json", new=AsyncMock()),
    ):
        response = await plain_client.get("/tickers/ZZZZZ/indicators")
    assert response.status_code == 404


# ── /technical tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_technical_200_shape(seeded_client: AsyncClient) -> None:
    """GET /technical returns 200 with all required top-level keys."""
    response = await seeded_client.get("/tickers/TECH/technical")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "TECH"
    assert body["timeframe"] == "1d"
    assert "score" in body
    assert "levels" in body
    assert "indicators_input" in body


@pytest.mark.asyncio
async def test_technical_score_block(seeded_client: AsyncClient) -> None:
    """Score block contains overall, subscores, and weights_version."""
    response = await seeded_client.get("/tickers/TECH/technical")
    assert response.status_code == 200
    score = response.json()["score"]
    assert "overall" in score
    assert "trend" in score
    assert "momentum" in score
    assert "mean_reversion" in score
    assert "weights_version" in score
    assert isinstance(score["weights_version"], str)


@pytest.mark.asyncio
async def test_technical_uptrend_score_high(seeded_client: AsyncClient) -> None:
    """250-bar uptrend produces trend subscore > 65."""
    response = await seeded_client.get("/tickers/TECH/technical")
    assert response.status_code == 200
    score = response.json()["score"]
    assert score["trend"] is not None
    assert score["trend"] > 65.0, f"Expected trend > 65, got {score['trend']}"


@pytest.mark.asyncio
async def test_technical_indicators_input_has_close(seeded_client: AsyncClient) -> None:
    """indicators_input block includes a positive close price."""
    response = await seeded_client.get("/tickers/TECH/technical")
    assert response.status_code == 200
    inp = response.json()["indicators_input"]
    assert inp["close"] > 0.0


@pytest.mark.asyncio
async def test_technical_weekly_timeframe(seeded_client: AsyncClient) -> None:
    """?timeframe=1w returns a valid technical result."""
    response = await seeded_client.get("/tickers/TECH/technical?timeframe=1w")
    assert response.status_code == 200
    body = response.json()
    assert body["timeframe"] == "1w"
    assert "score" in body


@pytest.mark.asyncio
async def test_technical_case_insensitive(seeded_client: AsyncClient) -> None:
    """Symbol lookup is case-insensitive."""
    response = await seeded_client.get("/tickers/tech/technical")
    assert response.status_code == 200
    assert response.json()["symbol"] == "TECH"


@pytest.mark.asyncio
async def test_technical_404_unknown_ticker(plain_client: AsyncClient) -> None:
    """GET /technical for an unknown symbol returns 404."""
    with (
        patch("app.services.technical.service.cache.get_json", new=AsyncMock(return_value=None)),
        patch("app.services.technical.service.cache.set_json", new=AsyncMock()),
    ):
        response = await plain_client.get("/tickers/ZZZZZ/technical")
    assert response.status_code == 404
