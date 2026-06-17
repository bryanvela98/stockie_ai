"""
Description: Pure indicator calculators for the technical analysis module.
             All functions operate on ordered pandas Series (oldest→newest) derived
             from PriceBar rows via `bars_to_frame()`. No DB or network access.
             Returns plain Python values (float | None) or aligned lists; pandas
             objects never cross the public API boundary. Each calculator documents
             its minimum lookback and returns None for insufficient history — never
             fabricates values or raises on short series.

             Indicator backend: pandas-ta-classic (numpy 2.x-compatible fork).
             See services/technical/__init__.py and pyproject.toml for rationale.

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; SMA/EMA/RSI/MACD/Bollinger/ATR calculators (Sprint 4-A2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import pandas_ta_classic as ta

if TYPE_CHECKING:
    from app.models.price_bar import PriceBar as PriceBarModel

# ── Default periods ────────────────────────────────────────────────────────────
# Named constants so callers and tests can reference them without magic numbers.
SMA_SHORT_PERIOD: int = 20
SMA_MID_PERIOD: int = 50
SMA_LONG_PERIOD: int = 200

EMA_SHORT_PERIOD: int = 12
EMA_LONG_PERIOD: int = 26

RSI_PERIOD: int = 14  # standard Wilder period
RSI_MIN_BARS: int = RSI_PERIOD + 1  # needs one extra bar to seed

MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9
MACD_MIN_BARS: int = MACD_SLOW + MACD_SIGNAL  # 35 bars minimum

BBANDS_PERIOD: int = 20
BBANDS_STD: float = 2.0
BBANDS_MIN_BARS: int = BBANDS_PERIOD

ATR_PERIOD: int = 14
ATR_MIN_BARS: int = ATR_PERIOD + 1


# ── Return types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndicatorResult:
    """Latest value and aligned historical series for a scalar indicator."""

    value: float | None
    """Latest indicator value, or None if insufficient history."""

    series: list[float | None]
    """Full aligned series (one entry per bar, NaN-seeded entries converted to None)."""


@dataclass(frozen=True)
class MacdResult:
    """Latest MACD line, signal, and histogram values plus aligned series."""

    macd: float | None
    signal: float | None
    histogram: float | None
    macd_series: list[float | None]
    signal_series: list[float | None]
    histogram_series: list[float | None]


@dataclass(frozen=True)
class BollingerResult:
    """Latest Bollinger Band values plus aligned series.

    Attributes:
        upper: Upper band (mid + std * σ).
        mid: Middle band (rolling SMA).
        lower: Lower band (mid - std * σ).
        percent_b: %B — position within bands: 0 = at lower, 1 = at upper.
        upper_series: Full aligned upper-band series.
        mid_series: Full aligned middle-band series.
        lower_series: Full aligned lower-band series.
    """

    upper: float | None
    mid: float | None
    lower: float | None
    percent_b: float | None
    upper_series: list[float | None]
    mid_series: list[float | None]
    lower_series: list[float | None]


# ── DataFrame adapter ──────────────────────────────────────────────────────────


def bars_to_frame(bars: list[PriceBarModel]) -> pd.DataFrame:
    """Convert ORM PriceBar rows into a float DataFrame sorted oldest→newest.

    Args:
        bars: PriceBar ORM instances in any order.

    Returns:
        DataFrame with float columns (open, high, low, close, volume, adjusted_close)
        indexed by timestamp, sorted ascending.
    """
    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "adjusted_close"])

    rows = [
        {
            "timestamp": b.timestamp,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume),
            "adjusted_close": float(b.adjusted_close) if b.adjusted_close is not None else None,
        }
        for b in bars
    ]
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df.set_index("timestamp", inplace=True)
    return df


# ── Internal helpers ───────────────────────────────────────────────────────────


def _series_to_list(s: pd.Series) -> list[float | None]:
    """Convert a pandas Series to list[float | None], replacing NaN with None."""
    return [None if pd.isna(v) else float(v) for v in s]


def _latest(s: pd.Series) -> float | None:
    """Return the last non-NaN value in a Series, or None if the series is all NaN."""
    valid = s.dropna()
    return float(valid.iloc[-1]) if not valid.empty else None


# ── Public calculators ─────────────────────────────────────────────────────────


def sma(close: pd.Series, period: int = SMA_SHORT_PERIOD) -> IndicatorResult:
    """Simple Moving Average of the close series.

    Args:
        close: Ordered close-price Series (oldest→newest), length ≥ period.
        period: Lookback window. Minimum bars = period. Defaults to SMA_SHORT_PERIOD.

    Returns:
        IndicatorResult with latest SMA value and full aligned series.
        Value is None when len(close) < period.
    """
    if len(close) < period:
        return IndicatorResult(value=None, series=[None] * len(close))

    result = ta.sma(close, length=period)
    return IndicatorResult(value=_latest(result), series=_series_to_list(result))


def ema(close: pd.Series, period: int = EMA_SHORT_PERIOD) -> IndicatorResult:
    """Exponential Moving Average of the close series.

    Args:
        close: Ordered close-price Series (oldest→newest), length ≥ period.
        period: Lookback window. Minimum bars = period. Defaults to EMA_SHORT_PERIOD.

    Returns:
        IndicatorResult with latest EMA value and full aligned series.
        Value is None when len(close) < period.
    """
    if len(close) < period:
        return IndicatorResult(value=None, series=[None] * len(close))

    result = ta.ema(close, length=period)
    return IndicatorResult(value=_latest(result), series=_series_to_list(result))


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> IndicatorResult:
    """Relative Strength Index (Wilder smoothing).

    Args:
        close: Ordered close-price Series (oldest→newest). Minimum bars = period + 1.
        period: RSI lookback. Defaults to RSI_PERIOD (14).

    Returns:
        IndicatorResult with latest RSI value (0–100) and full aligned series.
        Value is None when len(close) < period + 1.
    """
    min_bars = period + 1
    if len(close) < min_bars:
        return IndicatorResult(value=None, series=[None] * len(close))

    result = ta.rsi(close, length=period)
    return IndicatorResult(value=_latest(result), series=_series_to_list(result))


def macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> MacdResult:
    """MACD line, signal line, and histogram.

    Args:
        close: Ordered close-price Series (oldest→newest). Minimum bars = slow + signal.
        fast: Fast EMA period. Defaults to MACD_FAST (12).
        slow: Slow EMA period. Defaults to MACD_SLOW (26).
        signal: Signal EMA period. Defaults to MACD_SIGNAL (9).

    Returns:
        MacdResult with latest MACD/signal/histogram values and aligned series.
        All values are None when len(close) < slow + signal.
    """
    min_bars = slow + signal
    none_series: list[float | None] = [None] * len(close)
    if len(close) < min_bars:
        return MacdResult(
            macd=None,
            signal=None,
            histogram=None,
            macd_series=none_series,
            signal_series=none_series,
            histogram_series=none_series,
        )

    df = ta.macd(close, fast=fast, slow=slow, signal=signal)
    macd_col = f"MACD_{fast}_{slow}_{signal}"
    hist_col = f"MACDh_{fast}_{slow}_{signal}"
    sig_col = f"MACDs_{fast}_{slow}_{signal}"

    return MacdResult(
        macd=_latest(df[macd_col]),
        signal=_latest(df[sig_col]),
        histogram=_latest(df[hist_col]),
        macd_series=_series_to_list(df[macd_col]),
        signal_series=_series_to_list(df[sig_col]),
        histogram_series=_series_to_list(df[hist_col]),
    )


def bollinger(
    close: pd.Series,
    period: int = BBANDS_PERIOD,
    std: float = BBANDS_STD,
) -> BollingerResult:
    """Bollinger Bands: upper, mid (SMA), lower, and %B position.

    Args:
        close: Ordered close-price Series (oldest→newest). Minimum bars = period.
        period: Lookback window for the middle band (SMA). Defaults to BBANDS_PERIOD (20).
        std: Number of standard deviations for the bands. Defaults to BBANDS_STD (2.0).

    Returns:
        BollingerResult with latest band values and aligned series.
        All values are None when len(close) < period.
    """
    none_series: list[float | None] = [None] * len(close)
    if len(close) < period:
        return BollingerResult(
            upper=None,
            mid=None,
            lower=None,
            percent_b=None,
            upper_series=none_series,
            mid_series=none_series,
            lower_series=none_series,
        )

    df = ta.bbands(close, length=period, std=std)
    lower_col = f"BBL_{period}_{std}"
    mid_col = f"BBM_{period}_{std}"
    upper_col = f"BBU_{period}_{std}"
    pct_col = f"BBP_{period}_{std}"

    return BollingerResult(
        upper=_latest(df[upper_col]),
        mid=_latest(df[mid_col]),
        lower=_latest(df[lower_col]),
        percent_b=_latest(df[pct_col]),
        upper_series=_series_to_list(df[upper_col]),
        mid_series=_series_to_list(df[mid_col]),
        lower_series=_series_to_list(df[lower_col]),
    )


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ATR_PERIOD,
) -> IndicatorResult:
    """Average True Range — a measure of volatility.

    Args:
        high: High-price Series (oldest→newest).
        low: Low-price Series (oldest→newest).
        close: Close-price Series (oldest→newest). Minimum bars = period + 1.
        period: ATR smoothing period. Defaults to ATR_PERIOD (14).

    Returns:
        IndicatorResult with latest ATR value and full aligned series.
        Value is None when len(close) < period + 1.
    """
    min_bars = period + 1
    if len(close) < min_bars:
        return IndicatorResult(value=None, series=[None] * len(close))

    result = ta.atr(high, low, close, length=period)
    return IndicatorResult(value=_latest(result), series=_series_to_list(result))
