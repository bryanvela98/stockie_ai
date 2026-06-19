"""
Description: TechnicalService — orchestrates the full technical analysis
             pipeline for a single ticker: loads daily price bars, resamples
             to the requested timeframe, runs indicator calculators, detects
             support/resistance levels, and scores the result.

             Two public methods:
               get_technical(symbol, timeframe) — full TechnicalResult with
                 score + subscores + S/R levels, served from Redis cache
                 (1h TTL, keyed on TECH_WEIGHTS_VERSION + data_as_of).
               get_indicators(symbol, timeframe, ...) — per-indicator blocks
                 for chart overlays; not cached (per-request compute).

             Cache key format:
               technical:v{TECH_WEIGHTS_VERSION}:{symbol}:{timeframe}:{data_as_of}
             Bumping TECH_WEIGHTS_VERSION auto-invalidates stale cached scores.
             Redis unavailability degrades to live compute (cache helper is no-op).

             S/R levels are always computed from daily bars regardless of the
             requested timeframe — daily pivots are the standard reference frame
             for support/resistance analysis.

             Secrets must come from .env (AppSettings). No credentials here.
Last Modified By: bvela
Created: 2026-06-18
Last Modified:
    2026-06-18 - File created; TechnicalResult, IndicatorsResult, TechnicalService (Sprint 4-B1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.data_providers.exceptions import TickerNotFoundError
from app.models.price_bar import PriceBar as PriceBarModel
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository
from app.scoring.technical import (
    TECH_WEIGHTS_VERSION,
    IndicatorsInput,
    TechnicalScore,
    score_technical,
)
from app.services.technical.indicators import (
    ATR_PERIOD,
    BBANDS_PERIOD,
    EMA_LONG_PERIOD,
    EMA_SHORT_PERIOD,
    RSI_PERIOD,
    SMA_LONG_PERIOD,
    SMA_MID_PERIOD,
    SMA_SHORT_PERIOD,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
)
from app.services.technical.levels import (
    DEFAULT_MAX_LEVELS,
    SupportResistanceLevel,
    detect_levels,
)
from app.services.technical.timeframe import (
    Timeframe,
    resample,
)

# ── Constants ──────────────────────────────────────────────────────────────────

CACHE_TTL_SECONDS: int = 3_600  # 1 hour — shorter than fundamentals (daily bars update)
BARS_LOOKBACK_DAYS: int = 550  # ~2.2 trading years; SMA-200 needs ≥200 bars + resample buffer
MAX_SERIES_POINTS: int = 500  # cap overlay series to prevent large payloads

VALID_INDICATORS: frozenset[str] = frozenset({"sma", "ema", "rsi", "macd", "bbands", "atr"})
DEFAULT_SMA_PERIODS: list[int] = [SMA_SHORT_PERIOD, SMA_MID_PERIOD, SMA_LONG_PERIOD]
DEFAULT_EMA_PERIODS: list[int] = [EMA_SHORT_PERIOD, EMA_LONG_PERIOD]


# ── Result value objects ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndicatorBlock:
    """A single scalar indicator with its latest value and optional overlay series."""

    period: int
    latest: float | None
    series: list[float | None] = field(default_factory=list)


@dataclass(frozen=True)
class MacdBlock:
    """MACD indicator: line, signal, histogram and optional overlay series."""

    macd: float | None
    signal: float | None
    histogram: float | None
    macd_series: list[float | None] = field(default_factory=list)
    signal_series: list[float | None] = field(default_factory=list)
    histogram_series: list[float | None] = field(default_factory=list)


@dataclass(frozen=True)
class BollingerBlock:
    """Bollinger Bands: upper/mid/lower bands, %B, and optional overlay series."""

    upper: float | None
    mid: float | None
    lower: float | None
    percent_b: float | None
    upper_series: list[float | None] = field(default_factory=list)
    mid_series: list[float | None] = field(default_factory=list)
    lower_series: list[float | None] = field(default_factory=list)


@dataclass(frozen=True)
class IndicatorsResult:
    """Assembled indicator payload for a single ticker + timeframe."""

    symbol: str
    timeframe: str
    data_as_of: datetime | None
    bar_count: int
    sma: list[IndicatorBlock]
    ema: list[IndicatorBlock]
    rsi: IndicatorBlock | None
    macd: MacdBlock | None
    bbands: BollingerBlock | None
    atr: IndicatorBlock | None


@dataclass(frozen=True)
class TechnicalResult:
    """Full technical analysis: score + S/R levels + indicator values used for scoring."""

    symbol: str
    timeframe: str
    data_as_of: datetime | None
    score: TechnicalScore
    levels: list[SupportResistanceLevel]
    indicators_input: IndicatorsInput

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for Redis JSON storage."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "data_as_of": self.data_as_of.isoformat() if self.data_as_of else None,
            "score": {
                "overall": self.score.overall,
                "trend": self.score.trend,
                "momentum": self.score.momentum,
                "mean_reversion": self.score.mean_reversion,
                "weights_version": self.score.weights_version,
                "contributing": self.score.contributing,
            },
            "levels": [
                {
                    "price": lv.price,
                    "kind": lv.kind,
                    "strength": lv.strength,
                    "last_touch": lv.last_touch.isoformat(),
                }
                for lv in self.levels
            ],
            "indicators_input": {
                "close": self.indicators_input.close,
                "sma_20": self.indicators_input.sma_20,
                "sma_50": self.indicators_input.sma_50,
                "sma_200": self.indicators_input.sma_200,
                "rsi_14": self.indicators_input.rsi_14,
                "macd_value": self.indicators_input.macd_value,
                "macd_signal": self.indicators_input.macd_signal,
                "macd_histogram": self.indicators_input.macd_histogram,
                "bb_percent_b": self.indicators_input.bb_percent_b,
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TechnicalResult:
        """Reconstruct from a plain dict (deserialised from Redis JSON cache)."""
        return cls(
            symbol=d["symbol"],
            timeframe=d["timeframe"],
            data_as_of=datetime.fromisoformat(d["data_as_of"]) if d.get("data_as_of") else None,
            score=TechnicalScore(
                overall=d["score"]["overall"],
                trend=d["score"]["trend"],
                momentum=d["score"]["momentum"],
                mean_reversion=d["score"]["mean_reversion"],
                weights_version=d["score"]["weights_version"],
                contributing=d["score"]["contributing"],
            ),
            levels=[
                SupportResistanceLevel(
                    price=lv["price"],
                    kind=lv["kind"],
                    strength=lv["strength"],
                    last_touch=datetime.fromisoformat(lv["last_touch"]),
                )
                for lv in d["levels"]
            ],
            indicators_input=IndicatorsInput(**d["indicators_input"]),
        )


# ── Internal helpers ───────────────────────────────────────────────────────────


def _extract_series(bars: list[Any]) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Extract (close, high, low) pd.Series from a bar list.

    Works with both PriceBarModel (Decimal fields) and ResampledBar (float
    fields) because float(Decimal) and float(float) are both valid.

    Args:
        bars: List of PriceBarModel or ResampledBar objects, oldest-first.

    Returns:
        Three pandas Series: close, high, low.
    """
    close = pd.Series([float(b.close) for b in bars])
    high = pd.Series([float(b.high) for b in bars])
    low = pd.Series([float(b.low) for b in bars])
    return close, high, low


# ── Service ────────────────────────────────────────────────────────────────────


class TechnicalService:
    """Assembles the full technical analysis payload for a ticker.

    Instantiate with an open AsyncSession; the session is used by the
    repository layer. Cache I/O is performed via `app.core.cache`.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an open async database session.

        Args:
            session: Active AsyncSession for repository queries.
        """
        self._session = session
        self._ticker_repo = TickerRepository(session)
        self._price_repo = PriceRepository(session)

    async def _load_daily_bars(self, symbol: str) -> tuple[list[PriceBarModel], datetime | None]:
        """Load daily price bars for the lookback window.

        Args:
            symbol: Upper-cased ticker symbol.

        Returns:
            (bars, data_as_of) — bars ordered oldest-first; data_as_of is the
            timestamp of the most-recent bar (None when the ticker has no bars).

        Raises:
            TickerNotFoundError: When the symbol is not in the tickers table.
        """
        ticker = await self._ticker_repo.get_by_symbol(symbol)
        if ticker is None:
            raise TickerNotFoundError(symbol)

        today = date.today()
        start = today - timedelta(days=BARS_LOOKBACK_DAYS)
        bars = await self._price_repo.get_bars(ticker.id, start=start, end=today)
        data_as_of = bars[-1].timestamp if bars else None
        return bars, data_as_of

    async def get_technical(
        self,
        symbol: str,
        timeframe: Timeframe = "1d",
    ) -> TechnicalResult:
        """Return the full technical analysis for a ticker.

        Checks Redis cache first (keyed on symbol + timeframe + TECH_WEIGHTS_VERSION
        + data_as_of). On a miss: loads daily bars, resamples, computes indicators,
        detects S/R levels, scores, writes to cache (1-hour TTL), and returns.

        A ticker with insufficient history returns a valid TechnicalResult with
        None subscores and an empty levels list rather than raising.

        Args:
            symbol: Ticker symbol (case-insensitive).
            timeframe: One of "1d", "1w", "1mo".

        Returns:
            TechnicalResult with score, S/R levels, and the indicator values used.

        Raises:
            TickerNotFoundError: When the symbol is unknown or has no price bars.
        """
        symbol = symbol.upper()
        raw_bars, data_as_of = await self._load_daily_bars(symbol)

        if not raw_bars:
            raise TickerNotFoundError(symbol)

        cache_key = (
            f"technical:v{TECH_WEIGHTS_VERSION}:{symbol}:{timeframe}"
            f":{data_as_of.date().isoformat()}"  # type: ignore[union-attr]
        )
        cached = await cache.get_json(cache_key)
        if cached is not None:
            return TechnicalResult.from_dict(cached)

        bars_for_indicators: list[Any] = (
            resample(raw_bars, timeframe) if timeframe != "1d" else raw_bars
        )

        # Fall back to partial result when resampling yields nothing
        if not bars_for_indicators:
            empty_inp = IndicatorsInput(close=float(raw_bars[-1].close))
            result = TechnicalResult(
                symbol=symbol,
                timeframe=timeframe,
                data_as_of=data_as_of,
                score=score_technical(empty_inp),
                levels=[],
                indicators_input=empty_inp,
            )
            await cache.set_json(cache_key, result.to_dict(), ttl=CACHE_TTL_SECONDS)
            return result

        close, high, low = _extract_series(bars_for_indicators)

        sma20 = sma(close, SMA_SHORT_PERIOD)
        sma50 = sma(close, SMA_MID_PERIOD)
        sma200 = sma(close, SMA_LONG_PERIOD)
        rsi14 = rsi(close, RSI_PERIOD)
        macd_res = macd(close)
        bb = bollinger(close)

        inp = IndicatorsInput(
            close=float(close.iloc[-1]),
            sma_20=sma20.value,
            sma_50=sma50.value,
            sma_200=sma200.value,
            rsi_14=rsi14.value,
            macd_value=macd_res.macd,
            macd_signal=macd_res.signal,
            macd_histogram=macd_res.histogram,
            bb_percent_b=bb.percent_b,
        )

        # Levels always from daily bars — daily pivots are the standard reference frame
        levels = detect_levels(raw_bars, max_levels=DEFAULT_MAX_LEVELS)
        score = score_technical(inp)

        result = TechnicalResult(
            symbol=symbol,
            timeframe=timeframe,
            data_as_of=data_as_of,
            score=score,
            levels=levels,
            indicators_input=inp,
        )
        await cache.set_json(cache_key, result.to_dict(), ttl=CACHE_TTL_SECONDS)
        return result

    async def get_indicators(
        self,
        symbol: str,
        timeframe: Timeframe = "1d",
        requested: frozenset[str] | None = None,
        sma_periods: list[int] | None = None,
        ema_periods: list[int] | None = None,
        rsi_period: int = RSI_PERIOD,
        bbands_period: int = BBANDS_PERIOD,
        atr_period: int = ATR_PERIOD,
        include_series: bool = False,
    ) -> IndicatorsResult:
        """Return per-indicator latest values (and optional overlay series) for a ticker.

        Not cached — the caller controls which indicators and periods are computed,
        making a stable cache key impractical. Each call recomputes from stored bars.

        Args:
            symbol: Ticker symbol (case-insensitive).
            timeframe: One of "1d", "1w", "1mo".
            requested: Subset of VALID_INDICATORS to compute. Defaults to all.
            sma_periods: SMA periods to compute. Defaults to [20, 50, 200].
            ema_periods: EMA periods to compute. Defaults to [12, 26].
            rsi_period: RSI lookback period. Default 14.
            bbands_period: Bollinger Bands period. Default 20.
            atr_period: ATR lookback period. Default 14.
            include_series: When True, each block includes a series array capped
                at MAX_SERIES_POINTS points (oldest-to-newest).

        Returns:
            IndicatorsResult with the requested indicator blocks.

        Raises:
            TickerNotFoundError: When the symbol is unknown.
        """
        symbol = symbol.upper()
        active = requested if requested is not None else VALID_INDICATORS
        sma_ps = sma_periods if sma_periods is not None else DEFAULT_SMA_PERIODS
        ema_ps = ema_periods if ema_periods is not None else DEFAULT_EMA_PERIODS

        raw_bars, data_as_of = await self._load_daily_bars(symbol)

        bars_for_indicators: list[Any] = (
            resample(raw_bars, timeframe) if timeframe != "1d" else raw_bars
        )

        if not bars_for_indicators:
            return IndicatorsResult(
                symbol=symbol,
                timeframe=timeframe,
                data_as_of=data_as_of,
                bar_count=0,
                sma=[],
                ema=[],
                rsi=None,
                macd=None,
                bbands=None,
                atr=None,
            )

        close, high, low = _extract_series(bars_for_indicators)

        def _tail(s: list[float | None]) -> list[float | None]:
            return s[-MAX_SERIES_POINTS:] if include_series else []

        sma_blocks: list[IndicatorBlock] = []
        if "sma" in active:
            for p in sma_ps:
                r = sma(close, p)
                sma_blocks.append(IndicatorBlock(period=p, latest=r.value, series=_tail(r.series)))

        ema_blocks: list[IndicatorBlock] = []
        if "ema" in active:
            for p in ema_ps:
                r = ema(close, p)
                ema_blocks.append(IndicatorBlock(period=p, latest=r.value, series=_tail(r.series)))

        rsi_block: IndicatorBlock | None = None
        if "rsi" in active:
            r = rsi(close, rsi_period)
            rsi_block = IndicatorBlock(period=rsi_period, latest=r.value, series=_tail(r.series))

        macd_block: MacdBlock | None = None
        if "macd" in active:
            m = macd(close)
            macd_block = MacdBlock(
                macd=m.macd,
                signal=m.signal,
                histogram=m.histogram,
                macd_series=_tail(m.macd_series),
                signal_series=_tail(m.signal_series),
                histogram_series=_tail(m.histogram_series),
            )

        bbands_block: BollingerBlock | None = None
        if "bbands" in active:
            b = bollinger(close, period=bbands_period)
            bbands_block = BollingerBlock(
                upper=b.upper,
                mid=b.mid,
                lower=b.lower,
                percent_b=b.percent_b,
                upper_series=_tail(b.upper_series),
                mid_series=_tail(b.mid_series),
                lower_series=_tail(b.lower_series),
            )

        atr_block: IndicatorBlock | None = None
        if "atr" in active:
            r = atr(high, low, close, atr_period)
            atr_block = IndicatorBlock(period=atr_period, latest=r.value, series=_tail(r.series))

        return IndicatorsResult(
            symbol=symbol,
            timeframe=timeframe,
            data_as_of=data_as_of,
            bar_count=len(bars_for_indicators),
            sma=sma_blocks,
            ema=ema_blocks,
            rsi=rsi_block,
            macd=macd_block,
            bbands=bbands_block,
            atr=atr_block,
        )
