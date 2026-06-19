"""
Description: Technical analysis API router for Stockie AI.
             Exposes two endpoints under /tickers/{symbol}:

               GET /tickers/{symbol}/indicators
                   Per-indicator blocks (SMA, EMA, RSI, MACD, Bollinger, ATR)
                   for chart overlays. Supports multi-timeframe resampling and
                   optional full overlay series via ?series=true. Not cached —
                   per-request compute.

               GET /tickers/{symbol}/technical
                   Full technical analysis: trend/momentum/mean-reversion
                   subscores, overall score, support/resistance levels, and
                   the indicator values that drove the score.
                   Results are Redis-cached with a 1-hour TTL by TechnicalService.

             Query params for /indicators:
               timeframe: "1d" | "1w" | "1mo"  (default: "1d")
               indicators: comma-separated subset (default: all)
               sma_periods: comma-separated ints (default: 20,50,200)
               ema_periods: comma-separated ints (default: 12,26)
               rsi_period: int (default: 14)
               bbands_period: int (default: 20)
               atr_period: int (default: 14)
               series: bool (default: false) — include full overlay arrays

             Secrets must come from .env (AppSettings). No credentials here.
Last Modified By: bvela
Created: 2026-06-18
Last Modified:
    2026-06-18 - File created; indicators and technical endpoints (Sprint 4-B2/B3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.data_providers.exceptions import TickerNotFoundError
from app.services.technical.service import (
    VALID_INDICATORS,
    TechnicalService,
)

router = APIRouter(tags=["technical"])
_log = structlog.get_logger(__name__)


# ── Response models ───────────────────────────────────────────────────────────


class IndicatorBlockResponse(BaseModel):
    """A single scalar indicator (SMA or EMA period) with latest value and optional series."""

    period: int
    latest: float | None = None
    series: list[float | None] = []


class MacdBlockResponse(BaseModel):
    """MACD indicator values: line, signal, histogram and optional overlay series."""

    macd: float | None = None
    signal: float | None = None
    histogram: float | None = None
    macd_series: list[float | None] = []
    signal_series: list[float | None] = []
    histogram_series: list[float | None] = []


class BollingerBlockResponse(BaseModel):
    """Bollinger Bands: upper/mid/lower bands, %B, and optional overlay series."""

    upper: float | None = None
    mid: float | None = None
    lower: float | None = None
    percent_b: float | None = None
    upper_series: list[float | None] = []
    mid_series: list[float | None] = []
    lower_series: list[float | None] = []


class IndicatorsResponse(BaseModel):
    """Full indicator payload for a single ticker and timeframe."""

    symbol: str
    timeframe: str
    data_as_of: datetime | None = None
    bar_count: int
    sma: list[IndicatorBlockResponse] = []
    ema: list[IndicatorBlockResponse] = []
    rsi: IndicatorBlockResponse | None = None
    macd: MacdBlockResponse | None = None
    bbands: BollingerBlockResponse | None = None
    atr: IndicatorBlockResponse | None = None


class SupportResistanceLevelResponse(BaseModel):
    """A detected price level with kind and strength."""

    price: float
    kind: str
    strength: int
    last_touch: datetime


class TechnicalScoreResponse(BaseModel):
    """Technical score block: subscores (0–100) and the weights version."""

    overall: float | None = None
    trend: float | None = None
    momentum: float | None = None
    mean_reversion: float | None = None
    weights_version: str
    contributing: dict[str, float] = {}


class IndicatorsInputResponse(BaseModel):
    """Indicator snapshot used to derive the technical score (transparency)."""

    close: float
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    macd_value: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_percent_b: float | None = None


class TechnicalResponse(BaseModel):
    """Full technical analysis payload for a single ticker."""

    symbol: str
    timeframe: str
    data_as_of: datetime | None = None
    score: TechnicalScoreResponse
    levels: list[SupportResistanceLevelResponse] = []
    indicators_input: IndicatorsInputResponse


# ── Endpoint helpers ──────────────────────────────────────────────────────────


def _not_found(symbol: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Ticker not found: {symbol}")


def _parse_int_list(raw: str | None, default: list[int]) -> list[int]:
    """Parse a comma-separated string of ints, returning default on empty/None."""
    if not raw:
        return default
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return default


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/{symbol}/indicators", response_model=IndicatorsResponse)
async def get_indicators(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    timeframe: Annotated[str, Query(pattern="^(1d|1w|1mo)$")] = "1d",
    indicators: Annotated[str | None, Query()] = None,
    sma_periods: Annotated[str | None, Query()] = None,
    ema_periods: Annotated[str | None, Query()] = None,
    rsi_period: Annotated[int, Query(ge=2, le=50)] = 14,
    bbands_period: Annotated[int, Query(ge=2, le=50)] = 20,
    atr_period: Annotated[int, Query(ge=2, le=50)] = 14,
    series: Annotated[bool, Query()] = False,
) -> IndicatorsResponse:
    """Return per-indicator blocks for chart overlays.

    Supports multi-timeframe resampling and an optional full overlay series.
    Not cached — computed on every request.

    Args:
        symbol: Ticker symbol (case-insensitive).
        db: Injected async database session.
        timeframe: Bar interval — "1d", "1w", or "1mo".
        indicators: Comma-separated subset to include (default: all).
                    Valid values: sma, ema, rsi, macd, bbands, atr.
        sma_periods: Comma-separated SMA periods (default: "20,50,200").
        ema_periods: Comma-separated EMA periods (default: "12,26").
        rsi_period: RSI lookback period (default: 14).
        bbands_period: Bollinger Bands period (default: 20).
        atr_period: ATR period (default: 14).
        series: When true, include full overlay arrays (capped at 500 points).

    Returns:
        IndicatorsResponse with one block per requested indicator.

    Raises:
        HTTPException(404): When the symbol is unknown or has no price bars.
    """
    from app.services.technical.service import DEFAULT_EMA_PERIODS, DEFAULT_SMA_PERIODS

    requested: frozenset[str] | None = None
    if indicators:
        parsed = frozenset(x.strip().lower() for x in indicators.split(",") if x.strip())
        invalid = parsed - VALID_INDICATORS
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown indicators: {sorted(invalid)}. Valid: {sorted(VALID_INDICATORS)}",
            )
        requested = parsed

    sma_p = _parse_int_list(sma_periods, DEFAULT_SMA_PERIODS)
    ema_p = _parse_int_list(ema_periods, DEFAULT_EMA_PERIODS)

    service = TechnicalService(db)
    try:
        result = await service.get_indicators(
            symbol=symbol,
            timeframe=timeframe,  # type: ignore[arg-type]
            requested=requested,
            sma_periods=sma_p,
            ema_periods=ema_p,
            rsi_period=rsi_period,
            bbands_period=bbands_period,
            atr_period=atr_period,
            include_series=series,
        )
    except TickerNotFoundError:
        raise _not_found(symbol) from None

    return IndicatorsResponse(
        symbol=result.symbol,
        timeframe=result.timeframe,
        data_as_of=result.data_as_of,
        bar_count=result.bar_count,
        sma=[
            IndicatorBlockResponse(period=b.period, latest=b.latest, series=b.series)
            for b in result.sma
        ],
        ema=[
            IndicatorBlockResponse(period=b.period, latest=b.latest, series=b.series)
            for b in result.ema
        ],
        rsi=(
            IndicatorBlockResponse(
                period=result.rsi.period, latest=result.rsi.latest, series=result.rsi.series
            )
            if result.rsi is not None
            else None
        ),
        macd=(
            MacdBlockResponse(
                macd=result.macd.macd,
                signal=result.macd.signal,
                histogram=result.macd.histogram,
                macd_series=result.macd.macd_series,
                signal_series=result.macd.signal_series,
                histogram_series=result.macd.histogram_series,
            )
            if result.macd is not None
            else None
        ),
        bbands=(
            BollingerBlockResponse(
                upper=result.bbands.upper,
                mid=result.bbands.mid,
                lower=result.bbands.lower,
                percent_b=result.bbands.percent_b,
                upper_series=result.bbands.upper_series,
                mid_series=result.bbands.mid_series,
                lower_series=result.bbands.lower_series,
            )
            if result.bbands is not None
            else None
        ),
        atr=(
            IndicatorBlockResponse(
                period=result.atr.period, latest=result.atr.latest, series=result.atr.series
            )
            if result.atr is not None
            else None
        ),
    )


@router.get("/{symbol}/technical", response_model=TechnicalResponse)
async def get_technical(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    timeframe: Annotated[str, Query(pattern="^(1d|1w|1mo)$")] = "1d",
) -> TechnicalResponse:
    """Return the full technical analysis for a ticker.

    Includes trend/momentum/mean-reversion subscores, an overall score
    (all 0–100), support/resistance levels, and the indicator snapshot
    used for scoring (for UI transparency). Results are Redis-cached with
    a 1-hour TTL.

    Args:
        symbol: Ticker symbol (case-insensitive).
        db: Injected async database session.
        timeframe: Bar interval — "1d", "1w", or "1mo".

    Returns:
        TechnicalResponse with score, levels, and indicator inputs.

    Raises:
        HTTPException(404): When the symbol is unknown or has no price bars.
    """
    service = TechnicalService(db)
    try:
        result = await service.get_technical(symbol=symbol, timeframe=timeframe)  # type: ignore[arg-type]
    except TickerNotFoundError:
        raise _not_found(symbol) from None

    score = result.score
    inp = result.indicators_input

    return TechnicalResponse(
        symbol=result.symbol,
        timeframe=result.timeframe,
        data_as_of=result.data_as_of,
        score=TechnicalScoreResponse(
            overall=score.overall,
            trend=score.trend,
            momentum=score.momentum,
            mean_reversion=score.mean_reversion,
            weights_version=score.weights_version,
            contributing=score.contributing,
        ),
        levels=[
            SupportResistanceLevelResponse(
                price=lv.price,
                kind=lv.kind,
                strength=lv.strength,
                last_touch=lv.last_touch,
            )
            for lv in result.levels
        ],
        indicators_input=IndicatorsInputResponse(
            close=inp.close,
            sma_20=inp.sma_20,
            sma_50=inp.sma_50,
            sma_200=inp.sma_200,
            rsi_14=inp.rsi_14,
            macd_value=inp.macd_value,
            macd_signal=inp.macd_signal,
            macd_histogram=inp.macd_histogram,
            bb_percent_b=inp.bb_percent_b,
        ),
    )
