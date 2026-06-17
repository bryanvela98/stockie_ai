"""
Description: Unit tests for the pure indicator calculators in
             app.services.technical.indicators. All tests use in-memory
             pandas Series — no DB, no network. Covers reference value
             checks, short-series None guards, and NaN handling.
Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; indicator reference values + short-series guards (Sprint 4-A2).
"""

import pandas as pd
import pytest

from app.services.technical.indicators import (
    ATR_MIN_BARS,
    ATR_PERIOD,
    BBANDS_MIN_BARS,
    BBANDS_PERIOD,
    EMA_SHORT_PERIOD,
    MACD_MIN_BARS,
    RSI_MIN_BARS,
    RSI_PERIOD,
    SMA_SHORT_PERIOD,
    BollingerResult,
    IndicatorResult,
    MacdResult,
    atr,
    bars_to_frame,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _close(n: int, start: float = 10.0, step: float = 1.0) -> pd.Series:
    """Monotonically increasing close series of length n."""
    return pd.Series([start + i * step for i in range(n)])


def _ohlc(n: int, start: float = 10.0, step: float = 1.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (high, low, close) Series for ATR tests."""
    close = pd.Series([start + i * step for i in range(n)])
    high = close + 0.5
    low = close - 0.5
    return high, low, close


# ── bars_to_frame ──────────────────────────────────────────────────────────────


def test_bars_to_frame_empty_returns_empty_df() -> None:
    df = bars_to_frame([])
    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "adjusted_close"]


# ── SMA ────────────────────────────────────────────────────────────────────────


def test_sma_reference_value() -> None:
    """SMA(3) of [1,2,3,4,5] → last value = (3+4+5)/3 = 4.0."""
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(close, period=3)
    assert isinstance(result, IndicatorResult)
    assert result.value == pytest.approx(4.0, abs=1e-6)


def test_sma_series_length_matches_input() -> None:
    close = _close(30)
    result = sma(close, period=SMA_SHORT_PERIOD)
    assert len(result.series) == 30


def test_sma_series_none_for_warmup_bars() -> None:
    """First (period - 1) entries must be None (warmup)."""
    close = _close(25)
    result = sma(close, period=SMA_SHORT_PERIOD)
    assert result.series[: SMA_SHORT_PERIOD - 1] == [None] * (SMA_SHORT_PERIOD - 1)


def test_sma_short_series_returns_none() -> None:
    close = _close(SMA_SHORT_PERIOD - 1)
    result = sma(close, period=SMA_SHORT_PERIOD)
    assert result.value is None
    assert all(v is None for v in result.series)


# ── EMA ────────────────────────────────────────────────────────────────────────


def test_ema_reference_value() -> None:
    """EMA(3) of [1,2,3,4,5]: SMA-seeded; seed=SMA([1,2,3])=2.0, k=0.5.
    EMA[3] = 4.0*0.5 + 2.0*0.5 = 3.0; EMA[4] = 5.0*0.5 + 3.0*0.5 = 4.0."""
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = ema(close, period=3)
    assert result.value == pytest.approx(4.0, abs=1e-6)


def test_ema_short_series_returns_none() -> None:
    close = _close(EMA_SHORT_PERIOD - 1)
    result = ema(close, period=EMA_SHORT_PERIOD)
    assert result.value is None
    assert all(v is None for v in result.series)


def test_ema_series_length_matches_input() -> None:
    close = _close(30)
    result = ema(close, period=EMA_SHORT_PERIOD)
    assert len(result.series) == 30


# ── RSI ────────────────────────────────────────────────────────────────────────


def test_rsi_monotone_up_returns_100() -> None:
    """A strictly increasing series has no losses → RSI = 100."""
    close = _close(30, step=1.0)
    result = rsi(close, period=RSI_PERIOD)
    assert result.value == pytest.approx(100.0, abs=1e-3)


def test_rsi_monotone_down_returns_0() -> None:
    """A strictly decreasing series has no gains → RSI = 0."""
    close = pd.Series([float(30 - i) for i in range(30)])
    result = rsi(close, period=RSI_PERIOD)
    assert result.value == pytest.approx(0.0, abs=1e-3)


def test_rsi_short_series_returns_none() -> None:
    close = _close(RSI_MIN_BARS - 1)
    result = rsi(close, period=RSI_PERIOD)
    assert result.value is None
    assert all(v is None for v in result.series)


def test_rsi_series_length_matches_input() -> None:
    close = _close(40)
    result = rsi(close, period=RSI_PERIOD)
    assert len(result.series) == 40


def test_rsi_value_in_bounds() -> None:
    """RSI must always be in [0, 100]."""

    rng = [float(i) + (i % 3) * 0.5 for i in range(50)]
    close = pd.Series(rng)
    result = rsi(close, period=RSI_PERIOD)
    assert result.value is not None
    assert 0.0 <= result.value <= 100.0


# ── MACD ───────────────────────────────────────────────────────────────────────


def test_macd_structure() -> None:
    close = _close(50)
    result = macd(close)
    assert isinstance(result, MacdResult)
    assert result.macd is not None
    assert result.signal is not None
    assert result.histogram is not None


def test_macd_histogram_equals_macd_minus_signal() -> None:
    """histogram = MACD line - signal line."""
    close = _close(50)
    result = macd(close)
    assert result.histogram == pytest.approx(result.macd - result.signal, abs=1e-6)  # type: ignore[operator]


def test_macd_short_series_returns_none() -> None:
    close = _close(MACD_MIN_BARS - 1)
    result = macd(close)
    assert result.macd is None
    assert result.signal is None
    assert result.histogram is None
    assert all(v is None for v in result.macd_series)


def test_macd_series_lengths_match_input() -> None:
    close = _close(50)
    result = macd(close)
    assert len(result.macd_series) == 50
    assert len(result.signal_series) == 50
    assert len(result.histogram_series) == 50


# ── Bollinger Bands ────────────────────────────────────────────────────────────


def test_bollinger_structure() -> None:
    close = _close(40)
    result = bollinger(close)
    assert isinstance(result, BollingerResult)
    assert result.upper is not None
    assert result.mid is not None
    assert result.lower is not None


def test_bollinger_bands_ordering() -> None:
    """upper ≥ mid ≥ lower for any valid result."""
    close = _close(40)
    result = bollinger(close)
    assert result.upper >= result.mid >= result.lower  # type: ignore[operator]


def test_bollinger_percent_b_for_close_above_mid() -> None:
    """On a monotone-up series, the latest close is above the mid; %B > 0.5."""
    close = _close(40)
    result = bollinger(close)
    assert result.percent_b is not None
    assert result.percent_b > 0.5


def test_bollinger_short_series_returns_none() -> None:
    close = _close(BBANDS_MIN_BARS - 1)
    result = bollinger(close, period=BBANDS_PERIOD)
    assert result.upper is None
    assert result.mid is None
    assert result.lower is None
    assert all(v is None for v in result.upper_series)


def test_bollinger_series_lengths_match_input() -> None:
    close = _close(40)
    result = bollinger(close)
    assert len(result.upper_series) == 40
    assert len(result.mid_series) == 40
    assert len(result.lower_series) == 40


# ── ATR ────────────────────────────────────────────────────────────────────────


def test_atr_constant_range_equals_range() -> None:
    """When close is flat and high-low span is constant 1.0, ATR converges to 1.0.

    Uses a flat close so there is no inter-bar gap: true range = high - low = 1.0 always.
    """
    n = 30
    close = pd.Series([10.0] * n)  # flat close — no gap component
    high = close + 0.5
    low = close - 0.5
    result = atr(high, low, close, period=ATR_PERIOD)
    assert result.value == pytest.approx(1.0, abs=0.01)


def test_atr_short_series_returns_none() -> None:
    n = ATR_MIN_BARS - 1
    close = _close(n)
    high = close + 0.5
    low = close - 0.5
    result = atr(high, low, close, period=ATR_PERIOD)
    assert result.value is None
    assert all(v is None for v in result.series)


def test_atr_series_length_matches_input() -> None:
    n = 40
    high, low, close = _ohlc(n)
    result = atr(high, low, close, period=ATR_PERIOD)
    assert len(result.series) == n


def test_atr_positive_value() -> None:
    """ATR is always non-negative."""
    high, low, close = _ohlc(40)
    result = atr(high, low, close)
    assert result.value is not None
    assert result.value >= 0.0
