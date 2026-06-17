"""
Description: Unit tests for the technical scoring engine in app.scoring.technical.
             Covers normalize(), per-subscore behavior (uptrend/downtrend/neutral),
             None-signal renormalization, monotonicity, overall weighting, and
             TECH_WEIGHTS_VERSION stamp.
Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; technical scoring unit tests (Sprint 4-A5).
"""

from __future__ import annotations

import pytest

from app.scoring.technical import (
    TECH_WEIGHTS_VERSION,
    IndicatorsInput,
    TechnicalScore,
    normalize,
    score_mean_reversion,
    score_momentum,
    score_technical,
    score_trend,
)

# ── normalize() ────────────────────────────────────────────────────────────────


def test_normalize_at_floor_returns_0() -> None:
    assert normalize(0.0, floor=0.0, cap=1.0, higher_is_better=True) == pytest.approx(0.0)


def test_normalize_at_cap_returns_100() -> None:
    assert normalize(1.0, floor=0.0, cap=1.0, higher_is_better=True) == pytest.approx(100.0)


def test_normalize_midpoint_returns_50() -> None:
    assert normalize(0.5, floor=0.0, cap=1.0, higher_is_better=True) == pytest.approx(50.0)


def test_normalize_below_floor_clamps_to_0() -> None:
    assert normalize(-1.0, floor=0.0, cap=1.0, higher_is_better=True) == pytest.approx(0.0)


def test_normalize_above_cap_clamps_to_100() -> None:
    assert normalize(2.0, floor=0.0, cap=1.0, higher_is_better=True) == pytest.approx(100.0)


def test_normalize_inverted_at_floor_returns_100() -> None:
    """Lower-is-better: at floor (best raw value) should give score 100."""
    assert normalize(0.0, floor=0.0, cap=1.0, higher_is_better=False) == pytest.approx(100.0)


def test_normalize_inverted_at_cap_returns_0() -> None:
    assert normalize(1.0, floor=0.0, cap=1.0, higher_is_better=False) == pytest.approx(0.0)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _uptrend_input() -> IndicatorsInput:
    """All signals point strongly bullish."""
    return IndicatorsInput(
        close=120.0,
        sma_20=110.0,  # close 9% above SMA20 → high trend signal
        sma_50=100.0,  # close 20% above SMA50 → high trend signal
        sma_200=90.0,  # close 33% above SMA200 → high trend signal (capped at 100)
        rsi_14=70.0,  # strong momentum
        macd_value=2.0,
        macd_signal=1.0,  # MACD above signal → bullish cross
        macd_histogram=1.0,
        bb_percent_b=0.9,  # near upper band (uptrend)
    )


def _downtrend_input() -> IndicatorsInput:
    """All signals point strongly bearish."""
    return IndicatorsInput(
        close=80.0,
        sma_20=90.0,  # close 11% below SMA20 → bearish trend
        sma_50=100.0,  # close 20% below SMA50 → bearish trend
        sma_200=110.0,  # close well below SMA200 → bearish trend
        rsi_14=25.0,  # weak momentum
        macd_value=-2.0,
        macd_signal=-1.0,  # MACD below signal → bearish cross
        macd_histogram=-1.0,
        bb_percent_b=0.1,  # near lower band (downtrend)
    )


def _neutral_input() -> IndicatorsInput:
    """All signals neutral — close at SMAs, RSI=50, histogram=0, %B=0.5."""
    return IndicatorsInput(
        close=100.0,
        sma_20=100.0,
        sma_50=100.0,
        sma_200=100.0,
        rsi_14=50.0,
        macd_value=0.0,
        macd_signal=0.0,
        macd_histogram=0.0,
        bb_percent_b=0.5,
    )


# ── Trend subscore ────────────────────────────────────────────────────────────


def test_trend_uptrend_scores_high() -> None:
    result = score_trend(_uptrend_input())
    assert result is not None
    assert result.score > 70.0, f"Expected trend > 70, got {result.score}"


def test_trend_downtrend_scores_low() -> None:
    result = score_trend(_downtrend_input())
    assert result is not None
    assert result.score < 30.0, f"Expected trend < 30, got {result.score}"


def test_trend_neutral_scores_mid() -> None:
    result = score_trend(_neutral_input())
    assert result is not None
    assert 40.0 <= result.score <= 60.0, f"Expected trend ~50, got {result.score}"


def test_trend_none_when_all_signals_absent() -> None:
    inp = IndicatorsInput(close=100.0)  # no SMA, no MACD
    result = score_trend(inp)
    assert result is None


def test_trend_renormalizes_when_some_signals_absent() -> None:
    """Partial signals should still produce a valid subscore."""
    inp = IndicatorsInput(close=110.0, sma_20=100.0)  # only SMA20 available
    result = score_trend(inp)
    assert result is not None
    assert 0.0 <= result.score <= 100.0


# ── Momentum subscore ─────────────────────────────────────────────────────────


def test_momentum_uptrend_scores_high() -> None:
    result = score_momentum(_uptrend_input())
    assert result is not None
    assert result.score > 60.0


def test_momentum_downtrend_scores_low() -> None:
    result = score_momentum(_downtrend_input())
    assert result is not None
    assert result.score < 40.0


def test_momentum_none_when_all_absent() -> None:
    inp = IndicatorsInput(close=100.0)  # no RSI, no MACD
    result = score_momentum(inp)
    assert result is None


def test_momentum_rsi_only_valid() -> None:
    inp = IndicatorsInput(close=100.0, rsi_14=70.0)
    result = score_momentum(inp)
    assert result is not None
    assert result.score == pytest.approx(70.0, abs=1.0)  # RSI maps directly


# ── Mean-reversion subscore ───────────────────────────────────────────────────


def test_mean_reversion_oversold_scores_high() -> None:
    """Near lower band (%B≈0) = oversold = high mean-reversion buy signal."""
    inp = IndicatorsInput(close=100.0, bb_percent_b=0.05)
    result = score_mean_reversion(inp)
    assert result is not None
    assert result.score > 85.0


def test_mean_reversion_overbought_scores_low() -> None:
    """Near upper band (%B≈1) = overbought = low mean-reversion buy signal."""
    inp = IndicatorsInput(close=100.0, bb_percent_b=0.95)
    result = score_mean_reversion(inp)
    assert result is not None
    assert result.score < 15.0


def test_mean_reversion_none_when_absent() -> None:
    inp = IndicatorsInput(close=100.0)  # no bb_percent_b
    result = score_mean_reversion(inp)
    assert result is None


# ── score_technical() ─────────────────────────────────────────────────────────


def test_score_technical_structure() -> None:
    result = score_technical(_uptrend_input())
    assert isinstance(result, TechnicalScore)
    assert result.overall is not None
    assert result.trend is not None
    assert result.momentum is not None
    assert result.mean_reversion is not None
    assert result.weights_version == TECH_WEIGHTS_VERSION


def test_score_technical_uptrend_overall_high() -> None:
    result = score_technical(_uptrend_input())
    assert result.overall is not None
    assert result.overall > 60.0


def test_score_technical_downtrend_overall_low() -> None:
    result = score_technical(_downtrend_input())
    assert result.overall is not None
    assert result.overall < 40.0


def test_score_technical_neutral_overall_mid() -> None:
    result = score_technical(_neutral_input())
    assert result.overall is not None
    assert 35.0 <= result.overall <= 65.0


def test_score_technical_none_when_all_signals_absent() -> None:
    """No indicators at all → all subscores None → overall None."""
    inp = IndicatorsInput(close=100.0)
    result = score_technical(inp)
    assert result.overall is None
    assert result.trend is None
    assert result.momentum is None
    assert result.mean_reversion is None


def test_score_technical_partial_signals_not_zero() -> None:
    """Missing signals must be excluded (renormalized), never treated as 0."""
    inp_full = _uptrend_input()
    inp_partial = IndicatorsInput(
        close=inp_full.close,
        sma_20=inp_full.sma_20,
        rsi_14=inp_full.rsi_14,
        bb_percent_b=inp_full.bb_percent_b,
        # sma_50, sma_200, MACD all absent
    )
    result_partial = score_technical(inp_partial)
    assert result_partial.overall is not None
    # Partial uptrend signals should still produce a high overall (not dragged to 0)
    assert result_partial.overall > 50.0


# ── Monotonicity ──────────────────────────────────────────────────────────────


def test_trend_monotone_stronger_uptrend_never_lowers_score() -> None:
    """A stronger bullish trend must never decrease the trend subscore."""
    weak = score_trend(IndicatorsInput(close=105.0, sma_20=100.0))
    strong = score_trend(IndicatorsInput(close=115.0, sma_20=100.0))
    assert weak is not None and strong is not None
    assert strong.score >= weak.score


def test_overall_in_valid_range() -> None:
    for inp in [_uptrend_input(), _downtrend_input(), _neutral_input()]:
        result = score_technical(inp)
        assert result.overall is not None
        assert 0.0 <= result.overall <= 100.0


def test_weights_version_is_stamped() -> None:
    result = score_technical(_neutral_input())
    assert result.weights_version == TECH_WEIGHTS_VERSION
    assert len(result.weights_version) > 0
