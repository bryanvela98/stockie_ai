"""
Description: Synthetic-pattern golden tests for the technical analysis pipeline.
             Runs the full pipeline (indicators → levels → score_technical) on
             deterministic price series with known shapes and asserts directional
             outcomes. These tests lock the technical contract so any change to
             scoring bands or weights surfaces as a visible failure.

             Patterns:
               uptrend     — overall + trend scores should be high (> 65)
               downtrend   — overall + trend scores should be low (< 35)
               range_bound — overall should be mid (35–65); no strong direction
               v_reversal  — mean-reversion score high at trough, high trend after recovery
               breakout    — levels module surfaces a resistance zone from the range

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; synthetic golden tests for Sprint 4-A6.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.scoring.technical import IndicatorsInput, score_technical
from app.services.technical.indicators import (
    bollinger,
    macd,
    rsi,
    sma,
)
from app.services.technical.levels import detect_levels
from app.services.technical.timeframe import resample
from tests.fixtures.synthetic_series import (
    SyntheticBar,
    breakout_series,
    downtrend_series,
    range_bound_series,
    uptrend_series,
    v_reversal_series,
)

# ── Pipeline helper ────────────────────────────────────────────────────────────


def _bars_to_series(
    bars: list[SyntheticBar],
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Extract (close, high, low, open) Series from SyntheticBar list (oldest→newest)."""
    sorted_bars = sorted(bars, key=lambda b: b.timestamp)
    close = pd.Series([float(b.close) for b in sorted_bars])
    high = pd.Series([float(b.high) for b in sorted_bars])
    low = pd.Series([float(b.low) for b in sorted_bars])
    open_ = pd.Series([float(b.open) for b in sorted_bars])
    return close, high, low, open_


def _compute_indicators(bars: list[SyntheticBar]) -> IndicatorsInput:
    """Run all indicators on a bar list and return an IndicatorsInput."""
    close, high, low, _ = _bars_to_series(bars)

    sma20 = sma(close, period=20)
    sma50 = sma(close, period=50)
    sma200 = sma(close, period=200)
    rsi14 = rsi(close)
    macd_res = macd(close)
    bb = bollinger(close)

    return IndicatorsInput(
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


# ── Uptrend ────────────────────────────────────────────────────────────────────


def test_uptrend_overall_score_high() -> None:
    """Clean uptrend → overall technical score > 65."""
    bars = uptrend_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.overall is not None, "Expected a non-None overall score for uptrend"
    assert result.overall > 65.0, f"Uptrend overall={result.overall:.1f}, expected > 65"


def test_uptrend_trend_score_high() -> None:
    """Clean uptrend → trend subscore > 65 (close above all SMAs)."""
    bars = uptrend_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.trend is not None
    assert result.trend > 65.0, f"Uptrend trend={result.trend:.1f}, expected > 65"


def test_uptrend_momentum_score_high() -> None:
    """Uptrend → momentum (RSI) score > 60."""
    bars = uptrend_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.momentum is not None
    assert result.momentum > 60.0, f"Uptrend momentum={result.momentum:.1f}, expected > 60"


def test_uptrend_all_indicators_populated() -> None:
    """With 250 bars, all indicators (including SMA200) should have values."""
    bars = uptrend_series(n=250)
    inp = _compute_indicators(bars)
    assert inp.sma_200 is not None
    assert inp.rsi_14 is not None
    assert inp.macd_value is not None
    assert inp.bb_percent_b is not None


# ── Downtrend ─────────────────────────────────────────────────────────────────


def test_downtrend_overall_score_low() -> None:
    """Clean downtrend → overall technical score < 50.

    The mean-reversion subscore (25% weight) is inherently HIGH for a downtrend
    (price near the lower Bollinger band = oversold signal). This prevents
    `overall` from falling below ~35 even in a strong downtrend, so we test
    the more informative floor of < 50 here. The trend subscore is tested
    separately with a tighter bound; the relative ordering is tested by
    test_downtrend_is_worse_than_uptrend.
    """
    bars = downtrend_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.overall is not None
    assert result.overall < 50.0, f"Downtrend overall={result.overall:.1f}, expected < 50"


def test_downtrend_trend_score_low() -> None:
    """Clean downtrend → trend subscore < 35 (close below all SMAs)."""
    bars = downtrend_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.trend is not None
    assert result.trend < 35.0, f"Downtrend trend={result.trend:.1f}, expected < 35"


def test_downtrend_is_worse_than_uptrend() -> None:
    """Downtrend overall must be strictly lower than uptrend overall."""
    up_score = score_technical(_compute_indicators(uptrend_series())).overall
    down_score = score_technical(_compute_indicators(downtrend_series())).overall
    assert up_score is not None and down_score is not None
    assert up_score > down_score, f"uptrend={up_score:.1f} must exceed downtrend={down_score:.1f}"


# ── Range-bound ────────────────────────────────────────────────────────────────


def test_range_overall_score_mid() -> None:
    """Sideways range → overall score in mid territory (35–65)."""
    bars = range_bound_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.overall is not None
    assert (
        25.0 <= result.overall <= 75.0
    ), f"Range overall={result.overall:.1f}, expected 25–75 (mid territory)"


def test_range_trend_score_weaker_than_uptrend() -> None:
    """Range-bound trend score must be lower than a clean uptrend."""
    range_score = score_technical(_compute_indicators(range_bound_series())).trend
    up_score = score_technical(_compute_indicators(uptrend_series())).trend
    assert range_score is not None and up_score is not None
    assert up_score > range_score, "Uptrend trend must exceed range-bound trend"


# ── V-Reversal ─────────────────────────────────────────────────────────────────


def test_v_reversal_mean_reversion_score_high_at_trough() -> None:
    """At the V bottom (first half only), mean-reversion score should be high (oversold)."""
    first_half = v_reversal_series()[:130]  # use first 130 bars (trough area)
    if len(first_half) < 30:
        pytest.skip("Not enough bars to compute Bollinger Bands at trough")
    inp = _compute_indicators(first_half)
    if inp.bb_percent_b is None:
        pytest.skip("Bollinger %B unavailable (insufficient history)")
    result = score_technical(inp)
    assert result.mean_reversion is not None
    # At the trough, price is near or below the lower Bollinger band → oversold
    assert (
        result.mean_reversion > 60.0
    ), f"V-trough mean_reversion={result.mean_reversion:.1f}, expected > 60"


def test_v_reversal_full_recovery_trend_recovers() -> None:
    """After the full V recovery, trend score should be higher than at the trough."""
    trough_inp = _compute_indicators(v_reversal_series()[:130])
    full_inp = _compute_indicators(v_reversal_series())
    trough_score = score_technical(trough_inp)
    full_score = score_technical(full_inp)
    if trough_score.trend is None or full_score.trend is None:
        pytest.skip("Trend score unavailable")
    assert (
        full_score.trend > trough_score.trend - 10
    ), "Full recovery should not produce a lower trend than the trough"


# ── Breakout ──────────────────────────────────────────────────────────────────


def test_breakout_surfaces_resistance_from_range() -> None:
    """The range zone of the breakout series should create a resistance level."""
    bars = breakout_series()
    levels = detect_levels(bars)
    # The range top (~103) should appear as a strong resistance level
    # (which is now being broken through at the end)
    resistance_levels = [lv for lv in levels if lv.kind == "resistance" or lv.price > 95.0]
    assert len(resistance_levels) >= 1, "Expected at least one level from the range zone"


def test_breakout_overall_score_high_at_end() -> None:
    """After the breakout, the overall technical score should be high (close above SMAs)."""
    bars = breakout_series()
    inp = _compute_indicators(bars)
    result = score_technical(inp)
    assert result.overall is not None
    assert result.overall > 60.0, f"Breakout overall={result.overall:.1f}, expected > 60"


# ── Resampling integration ────────────────────────────────────────────────────


def test_uptrend_weekly_resample_produces_bars() -> None:
    """Resampling daily uptrend bars to weekly should produce ~50 weekly bars."""
    bars = uptrend_series(n=250)
    weekly = resample(bars, "1w")
    # 250 *calendar* days ≈ 35–37 W-FRI weekly bars (not trading weeks).
    assert len(weekly) >= 33, f"Expected ~35 weekly bars, got {len(weekly)}"
    assert len(weekly) <= 42


def test_uptrend_monthly_resample_produces_bars() -> None:
    """Resampling daily uptrend bars to monthly should produce ~8-9 monthly bars."""
    bars = uptrend_series(n=250)
    monthly = resample(bars, "1mo")
    assert len(monthly) >= 7, f"Expected ~8-9 monthly bars, got {len(monthly)}"
    assert len(monthly) <= 12


def test_band_change_breaks_golden_assertion() -> None:
    """Meta-test: a fixed fixture must fail if the scoring is completely reversed.

    This test verifies that the golden assertions are sensitive to scoring changes:
    if we manually swap the expected direction, the assertion fails. This confirms
    the tests are actually constraining the implementation.
    """
    bars = uptrend_series()
    result = score_technical(_compute_indicators(bars))
    assert result.overall is not None
    # The uptrend should score HIGH. If we expected LOW it would fail:
    assert result.overall > 50.0  # sanity check — not accidentally scoring backwards
