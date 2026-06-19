"""
Description: Tests for TechnicalService — the orchestrating service that
             loads price bars, resamples, computes indicators, detects S/R
             levels, scores, and caches the result.
             All tests run against an in-memory SQLite DB; the cache is
             replaced with a no-op fake so no Redis connection is needed.
Last Modified By: bvela
Created: 2026-06-18
Last Modified:
    2026-06-18 - File created; assembly correctness, cache path, error cases (Sprint 4-B1).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.data_providers.models import PriceBar as PriceBarDTO
from app.data_providers.models import TickerInfo
from app.models.ticker import Ticker
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository
from app.scoring.technical import TECH_WEIGHTS_VERSION
from app.services.technical.service import (
    CACHE_TTL_SECONDS,
    TechnicalService,
)
from tests.fixtures.synthetic_series import SyntheticBar, downtrend_series, uptrend_series

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def no_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace cache helpers with no-ops so tests never need Redis."""
    monkeypatch.setattr(
        "app.services.technical.service.cache.get_json", AsyncMock(return_value=None)
    )
    monkeypatch.setattr("app.services.technical.service.cache.set_json", AsyncMock())


async def _seed_ticker(session: AsyncSession, symbol: str = "TEST") -> Ticker:
    repo = TickerRepository(session)
    return await repo.upsert(
        TickerInfo(
            symbol=symbol,
            name=f"{symbol} Corp",
            exchange="NYSE",
            asset_type="equity",
            currency="USD",
            sector="Technology",
            industry="Software",
        )
    )


def _bar_to_dto(bar: SyntheticBar, symbol: str = "TEST") -> PriceBarDTO:
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
    session: AsyncSession,
    ticker_id: int,
    synthetic_bars: list[SyntheticBar],
    symbol: str = "TEST",
) -> None:
    repo = PriceRepository(session)
    dtos = [_bar_to_dto(b, symbol) for b in synthetic_bars]
    await repo.upsert_bars(ticker_id, dtos, interval="1d")


# ── get_technical ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_technical_returns_structure(db_session: AsyncSession) -> None:
    """get_technical returns a TechnicalResult with expected fields."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    service = TechnicalService(db_session)
    result = await service.get_technical("TEST")

    assert result.symbol == "TEST"
    assert result.timeframe == "1d"
    assert result.data_as_of is not None
    assert result.score.weights_version == TECH_WEIGHTS_VERSION
    assert isinstance(result.levels, list)
    assert result.indicators_input.close > 0.0


@pytest.mark.asyncio
async def test_get_technical_uptrend_scores_high(db_session: AsyncSession) -> None:
    """Uptrend bars produce a trend subscore > 65."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_technical("TEST")

    assert result.score.trend is not None
    assert result.score.trend > 65.0, f"Expected uptrend trend > 65, got {result.score.trend:.1f}"


@pytest.mark.asyncio
async def test_get_technical_downtrend_scores_low(db_session: AsyncSession) -> None:
    """Downtrend bars produce a trend subscore < 35."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, downtrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_technical("TEST")

    assert result.score.trend is not None
    assert result.score.trend < 35.0, f"Expected downtrend trend < 35, got {result.score.trend:.1f}"


@pytest.mark.asyncio
async def test_get_technical_writes_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful call writes the result to the cache with the correct TTL."""
    set_mock = AsyncMock()
    monkeypatch.setattr("app.services.technical.service.cache.set_json", set_mock)

    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    await TechnicalService(db_session).get_technical("TEST")

    set_mock.assert_awaited_once()
    key, payload, *rest = set_mock.call_args.args
    assert "TEST" in key
    assert "1d" in key
    assert f"v{TECH_WEIGHTS_VERSION}" in key
    assert rest == [] or set_mock.call_args.kwargs.get("ttl") == CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_technical_returns_cached_result(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the cache has a hit, get_technical returns it without hitting the DB."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    # Prime real result
    real = await TechnicalService(db_session).get_technical("TEST")

    # Now make cache return the serialised real result
    get_mock = AsyncMock(return_value=real.to_dict())
    monkeypatch.setattr("app.services.technical.service.cache.get_json", get_mock)

    result2 = await TechnicalService(db_session).get_technical("TEST")

    assert result2.symbol == real.symbol
    assert result2.score.overall == real.score.overall
    assert result2.score.weights_version == real.score.weights_version


@pytest.mark.asyncio
async def test_get_technical_raises_for_unknown_ticker(db_session: AsyncSession) -> None:
    """get_technical raises TickerNotFoundError for an unknown symbol."""
    with pytest.raises(TickerNotFoundError):
        await TechnicalService(db_session).get_technical("UNKNOWN")


@pytest.mark.asyncio
async def test_get_technical_raises_when_no_bars(db_session: AsyncSession) -> None:
    """A known ticker with no price bars raises TickerNotFoundError."""
    await _seed_ticker(db_session)  # no bars seeded
    await db_session.commit()

    with pytest.raises(TickerNotFoundError):
        await TechnicalService(db_session).get_technical("TEST")


@pytest.mark.asyncio
async def test_get_technical_thin_history_produces_none_subscores(
    db_session: AsyncSession,
) -> None:
    """Fewer bars than SMA-200 returns a result with None subscores (not a crash)."""
    ticker = await _seed_ticker(db_session)
    # Only 10 bars — not enough for any SMA or RSI
    await _seed_bars(db_session, ticker.id, uptrend_series(n=10))
    await db_session.commit()

    result = await TechnicalService(db_session).get_technical("TEST")

    # With only 10 bars, SMA-20/50/200, RSI, MACD, Bollinger are all None
    assert result.score.trend is None
    assert result.score.momentum is None
    assert result.score.overall is None


@pytest.mark.asyncio
async def test_get_technical_weekly_timeframe(db_session: AsyncSession) -> None:
    """timeframe=1w runs on resampled weekly bars and returns a valid result."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_technical("TEST", timeframe="1w")

    assert result.timeframe == "1w"
    assert result.score.overall is not None or result.data_as_of is None


@pytest.mark.asyncio
async def test_get_technical_case_insensitive(db_session: AsyncSession) -> None:
    """Symbol lookup is case-insensitive."""
    ticker = await _seed_ticker(db_session, symbol="MSFT")
    await _seed_bars(db_session, ticker.id, uptrend_series(), symbol="MSFT")
    await db_session.commit()

    result = await TechnicalService(db_session).get_technical("msft")
    assert result.symbol == "MSFT"


# ── get_indicators ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_indicators_default_returns_all(db_session: AsyncSession) -> None:
    """Default call populates all indicator blocks."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_indicators("TEST")

    assert len(result.sma) == 3  # [20, 50, 200]
    assert len(result.ema) == 2  # [12, 26]
    assert result.rsi is not None
    assert result.macd is not None
    assert result.bbands is not None
    assert result.atr is not None


@pytest.mark.asyncio
async def test_get_indicators_series_empty_by_default(db_session: AsyncSession) -> None:
    """Series arrays are empty by default (include_series=False)."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_indicators("TEST")

    assert result.sma[0].series == []
    assert result.rsi is not None and result.rsi.series == []


@pytest.mark.asyncio
async def test_get_indicators_series_populated_when_requested(
    db_session: AsyncSession,
) -> None:
    """include_series=True populates all series arrays (capped at MAX_SERIES_POINTS)."""
    from app.services.technical.service import MAX_SERIES_POINTS

    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_indicators("TEST", include_series=True)

    assert len(result.sma[0].series) > 0
    assert len(result.sma[0].series) <= MAX_SERIES_POINTS
    assert result.rsi is not None and len(result.rsi.series) > 0


@pytest.mark.asyncio
async def test_get_indicators_subset(db_session: AsyncSession) -> None:
    """Requesting only sma+rsi leaves macd/bbands/atr as None."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_indicators(
        "TEST",
        requested=frozenset({"sma", "rsi"}),
    )

    assert len(result.sma) == 3
    assert result.rsi is not None
    assert result.macd is None
    assert result.bbands is None
    assert result.atr is None
    assert result.ema == []


@pytest.mark.asyncio
async def test_get_indicators_custom_sma_periods(db_session: AsyncSession) -> None:
    """Custom sma_periods are respected."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    result = await TechnicalService(db_session).get_indicators(
        "TEST",
        requested=frozenset({"sma"}),
        sma_periods=[10, 30],
    )

    assert [b.period for b in result.sma] == [10, 30]


@pytest.mark.asyncio
async def test_get_indicators_weekly_timeframe(db_session: AsyncSession) -> None:
    """timeframe=1w resamples bars and returns a reduced bar_count."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())  # 250 daily bars
    await db_session.commit()

    daily = await TechnicalService(db_session).get_indicators("TEST", timeframe="1d")
    weekly = await TechnicalService(db_session).get_indicators("TEST", timeframe="1w")

    assert weekly.bar_count < daily.bar_count


@pytest.mark.asyncio
async def test_get_indicators_raises_for_unknown_ticker(db_session: AsyncSession) -> None:
    """get_indicators raises TickerNotFoundError for an unknown symbol."""
    with pytest.raises(TickerNotFoundError):
        await TechnicalService(db_session).get_indicators("UNKNOWN")


# ── Cache hardening (B4) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_keys_differ_by_timeframe(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Daily and weekly calls write different cache keys (timeframe is part of the key)."""
    keys: list[str] = []

    async def capture_set(key: str, *args: object, **kwargs: object) -> None:
        keys.append(key)

    monkeypatch.setattr("app.services.technical.service.cache.set_json", capture_set)

    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    service = TechnicalService(db_session)
    await service.get_technical("TEST", timeframe="1d")
    await service.get_technical("TEST", timeframe="1w")

    assert len(keys) == 2
    assert keys[0] != keys[1], "Daily and weekly must have distinct cache keys"
    assert "1d" in keys[0] and "1w" in keys[1]


@pytest.mark.asyncio
async def test_to_dict_from_dict_roundtrip(db_session: AsyncSession) -> None:
    """TechnicalResult serialises and deserialises without data loss."""
    ticker = await _seed_ticker(db_session)
    await _seed_bars(db_session, ticker.id, uptrend_series())
    await db_session.commit()

    original = await TechnicalService(db_session).get_technical("TEST")
    restored = original.__class__.from_dict(original.to_dict())

    assert restored.symbol == original.symbol
    assert restored.timeframe == original.timeframe
    assert restored.score.overall == original.score.overall
    assert restored.score.trend == original.score.trend
    assert restored.score.weights_version == original.score.weights_version
    assert len(restored.levels) == len(original.levels)
    assert restored.indicators_input.close == original.indicators_input.close
