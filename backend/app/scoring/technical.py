"""
Description: Technical scoring engine for Stockie AI.
             Converts computed indicator values (SMA/EMA cross-state, RSI,
             MACD, Bollinger %B) into three 0–100 subscores (Trend, Momentum,
             Mean-Reversion) and an overall TechnicalScore. Structurally mirrors
             scoring/fundamental.py so the two score types can be combined in
             the Sprint 6 recommendation engine.

             DESIGN PRINCIPLES:
             - Same normalization/weighting pattern as the fundamental scorer
               (normalize → weight → renormalize for None signals).
             - TECH_WEIGHTS_VERSION is stamped on every TechnicalScore.
             - Caller passes an IndicatorsInput dataclass; this module derives
               all sub-signals internally so the scorer is independent of the
               indicator calculator's implementation details.

             SIGNAL BANDS:
             All signals are expressed as a float in a natural range; the band
             clamps them to [0, 100] via the piecewise-linear normalize().

             TREND SIGNALS (higher = more bullish trend):
               close_vs_sma20:  (close/SMA20) - 1; floor=-0.10, cap=0.10
               close_vs_sma50:  (close/SMA50) - 1; floor=-0.10, cap=0.10
               close_vs_sma200: (close/SMA200) - 1; floor=-0.20, cap=0.20
               sma20_vs_sma50:  (SMA20/SMA50) - 1; floor=-0.05, cap=0.05
                                (golden-cross / death-cross state)
               macd_hist_pct:   macd_hist / close; floor=-0.02, cap=0.02

             TREND WEIGHTS:
               close_vs_sma20=20%, close_vs_sma50=20%, close_vs_sma200=20%,
               sma20_vs_sma50=20%, macd_hist_pct=20%

             MOMENTUM SIGNALS (higher = stronger bullish momentum):
               rsi:        RSI(14) direct; floor=0, cap=100
               macd_cross: 1.0 if MACD > signal else 0.0; floor=0, cap=1

             MOMENTUM WEIGHTS:
               rsi=60%, macd_cross=40%

             MEAN-REVERSION SIGNALS (higher = more oversold = stronger buy signal):
               bb_percent_b: Bollinger %B; floor=0, cap=1, higher_is_better=False
               (%B near 0 = at lower band = oversold = score 100)

             MEAN-REVERSION WEIGHTS:
               bb_percent_b=100%

             OVERALL WEIGHTS:
               trend=40%, momentum=35%, mean_reversion=25%

             NOTE ON RSI IN MOMENTUM:
             RSI is used as a raw momentum signal here (higher RSI = stronger
             momentum). The mean-reversion subscore handles the "overbought /
             oversold reversal" interpretation independently. The Sprint 6
             recommendation engine decides how to balance the two perspectives
             based on trading horizon (see docs/adr/0001-scores-combination.md).

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; TechnicalScore, IndicatorsInput, score_technical() (Sprint 4-A5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── version ────────────────────────────────────────────────────────────────────

# Increment this string whenever any band or weight constant changes so that
# stored scores can be compared against the version that produced them.
TECH_WEIGHTS_VERSION = "v1.0"

# ── normalization bands ────────────────────────────────────────────────────────
# Each entry: (floor, cap, higher_is_better)

_TREND_BANDS: dict[str, tuple[float, float, bool]] = {
    # Price relative to SMA (as % deviation): above SMA → bullish → not inverted
    "close_vs_sma20": (-0.10, 0.10, True),
    "close_vs_sma50": (-0.10, 0.10, True),
    "close_vs_sma200": (-0.20, 0.20, True),
    # Golden-cross state: SMA20 above SMA50 → bullish alignment → not inverted
    "sma20_vs_sma50": (-0.05, 0.05, True),
    # MACD histogram as % of close: positive → buying pressure → not inverted
    "macd_hist_pct": (-0.02, 0.02, True),
}

_MOMENTUM_BANDS: dict[str, tuple[float, float, bool]] = {
    # RSI direct (0–100): higher RSI = stronger bullish momentum
    "rsi": (0.0, 100.0, True),
    # MACD crossover state: 1.0 = MACD above signal, 0.0 = below
    "macd_cross": (0.0, 1.0, True),
}

_MEAN_REVERSION_BANDS: dict[str, tuple[float, float, bool]] = {
    # Bollinger %B: near 0 = at lower band = oversold = buy signal → inverted
    "bb_percent_b": (0.0, 1.0, False),
}

# ── subscore weights ───────────────────────────────────────────────────────────

_TREND_WEIGHTS: dict[str, float] = {
    "close_vs_sma20": 0.20,
    "close_vs_sma50": 0.20,
    "close_vs_sma200": 0.20,
    "sma20_vs_sma50": 0.20,
    "macd_hist_pct": 0.20,
}

_MOMENTUM_WEIGHTS: dict[str, float] = {
    "rsi": 0.60,
    "macd_cross": 0.40,
}

_MEAN_REVERSION_WEIGHTS: dict[str, float] = {
    "bb_percent_b": 1.00,
}

# Overall weights — must sum to 1.0.
_OVERALL_WEIGHTS: dict[str, float] = {
    "trend": 0.40,
    "momentum": 0.35,
    "mean_reversion": 0.25,
}

# ── output types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Subscore:
    """A single 0–100 subscore with contributing signal values for transparency."""

    score: float
    contributing: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TechnicalScore:
    """Complete technical score for a single ticker at a given timeframe.

    overall, trend, momentum, and mean_reversion are 0–100. Any subscore
    with no available inputs will be None (not 0). overall is None when
    all three subscores are None.
    """

    overall: float | None
    trend: float | None
    momentum: float | None
    mean_reversion: float | None
    weights_version: str
    # Raw derived signal values included for UI transparency
    contributing: dict[str, float] = field(default_factory=dict)


# ── input type ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndicatorsInput:
    """Computed indicator values consumed by the technical scorer.

    Each field is optional (None when insufficient history). The scorer
    excludes None signals and renormalizes surviving weights.

    Attributes:
        close: Current closing price (required for derived signal computation).
        sma_20: SMA(20) value, or None if insufficient history.
        sma_50: SMA(50) value, or None.
        sma_200: SMA(200) value, or None.
        rsi_14: RSI(14) value in [0, 100], or None.
        macd_value: MACD line value, or None.
        macd_signal: MACD signal line value, or None.
        macd_histogram: MACD histogram value, or None.
        bb_percent_b: Bollinger %B in [0, 1], or None.
    """

    close: float
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    macd_value: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_percent_b: float | None = None


# ── normalization (duplicated from scoring/fundamental.py) ─────────────────────
# Kept here deliberately — extracting to _common.py would require editing
# fundamental.py out of scope. These 15 lines beat a two-module dependency.


def normalize(value: float, floor: float, cap: float, higher_is_better: bool) -> float:
    """Map a raw value to a 0–100 score via piecewise-linear normalization.

    Args:
        value: Raw signal value.
        floor: Values ≤ floor map to raw score 0.
        cap: Values ≥ cap map to raw score 100.
        higher_is_better: When False, the score is inverted (100 − raw).

    Returns:
        Normalized score in [0, 100].
    """
    if cap == floor:
        raw = 100.0 if value >= cap else 0.0
    else:
        raw = (value - floor) / (cap - floor) * 100.0
        raw = max(0.0, min(100.0, raw))
    return (100.0 - raw) if not higher_is_better else raw


def _weighted_subscore(
    metric_values: dict[str, float | None],
    bands: dict[str, tuple[float, float, bool]],
    weights: dict[str, float],
) -> Subscore | None:
    """Compute a weighted subscore, renormalizing weights when signals are None.

    Args:
        metric_values: Dict of signal name → value (or None if unavailable).
        bands: Dict of signal name → (floor, cap, higher_is_better).
        weights: Dict of signal name → raw weight (should sum to 1.0).

    Returns:
        Subscore with the weighted average in [0, 100] and contributing signals,
        or None if all signals are None.
    """
    present: dict[str, float] = {}
    total_weight = 0.0

    for name, raw_value in metric_values.items():
        if raw_value is None:
            continue
        floor, cap, higher_is_better = bands[name]
        present[name] = normalize(raw_value, floor, cap, higher_is_better)
        total_weight += weights[name]

    if not present or total_weight == 0.0:
        return None

    score = sum(present[name] * weights[name] / total_weight for name in present)
    return Subscore(score=score, contributing=present)


# ── subscore functions ─────────────────────────────────────────────────────────


def _derive_trend_signals(inp: IndicatorsInput) -> dict[str, float | None]:
    """Derive trend sub-signals from indicator inputs."""
    c = inp.close
    signals: dict[str, float | None] = {}

    signals["close_vs_sma20"] = (c / inp.sma_20) - 1.0 if inp.sma_20 else None
    signals["close_vs_sma50"] = (c / inp.sma_50) - 1.0 if inp.sma_50 else None
    signals["close_vs_sma200"] = (c / inp.sma_200) - 1.0 if inp.sma_200 else None
    signals["sma20_vs_sma50"] = (
        (inp.sma_20 / inp.sma_50) - 1.0 if inp.sma_20 and inp.sma_50 else None
    )
    signals["macd_hist_pct"] = inp.macd_histogram / c if inp.macd_histogram is not None else None

    return signals


def _derive_momentum_signals(inp: IndicatorsInput) -> dict[str, float | None]:
    """Derive momentum sub-signals from indicator inputs."""
    macd_cross: float | None = None
    if inp.macd_value is not None and inp.macd_signal is not None:
        macd_cross = 1.0 if inp.macd_value > inp.macd_signal else 0.0

    return {
        "rsi": inp.rsi_14,
        "macd_cross": macd_cross,
    }


def _derive_mean_reversion_signals(inp: IndicatorsInput) -> dict[str, float | None]:
    """Derive mean-reversion sub-signals from indicator inputs."""
    return {"bb_percent_b": inp.bb_percent_b}


def score_trend(inp: IndicatorsInput) -> Subscore | None:
    """Compute the Trend subscore (0–100) from indicator inputs.

    Args:
        inp: Computed indicator values for the ticker.

    Returns:
        Trend Subscore, or None if all trend signals are unavailable.
    """
    return _weighted_subscore(_derive_trend_signals(inp), _TREND_BANDS, _TREND_WEIGHTS)


def score_momentum(inp: IndicatorsInput) -> Subscore | None:
    """Compute the Momentum subscore (0–100) from indicator inputs.

    Args:
        inp: Computed indicator values for the ticker.

    Returns:
        Momentum Subscore, or None if all momentum signals are unavailable.
    """
    return _weighted_subscore(_derive_momentum_signals(inp), _MOMENTUM_BANDS, _MOMENTUM_WEIGHTS)


def score_mean_reversion(inp: IndicatorsInput) -> Subscore | None:
    """Compute the Mean-Reversion subscore (0–100) from indicator inputs.

    Args:
        inp: Computed indicator values for the ticker.

    Returns:
        Mean-Reversion Subscore, or None if all mean-reversion signals are unavailable.
    """
    return _weighted_subscore(
        _derive_mean_reversion_signals(inp),
        _MEAN_REVERSION_BANDS,
        _MEAN_REVERSION_WEIGHTS,
    )


def score_technical(inp: IndicatorsInput) -> TechnicalScore:
    """Compute the full TechnicalScore from indicator inputs.

    Combines trend, momentum, and mean-reversion subscores into an overall
    0–100 technical score. Subscores with no signals are excluded from the
    overall; the surviving weights are renormalized.

    Args:
        inp: Computed indicator values for the ticker.

    Returns:
        TechnicalScore with trend, momentum, mean_reversion (each 0–100 or None),
        overall (0–100 or None), TECH_WEIGHTS_VERSION, and contributing signals.
    """
    trend_sub = score_trend(inp)
    momentum_sub = score_momentum(inp)
    mean_rev_sub = score_mean_reversion(inp)

    subscores: dict[str, float | None] = {
        "trend": trend_sub.score if trend_sub else None,
        "momentum": momentum_sub.score if momentum_sub else None,
        "mean_reversion": mean_rev_sub.score if mean_rev_sub else None,
    }

    # Weighted average of available subscores (renormalize on None).
    available = {k: v for k, v in subscores.items() if v is not None}
    overall: float | None = None
    if available:
        total_w = sum(_OVERALL_WEIGHTS[k] for k in available)
        if total_w > 0:
            overall = sum(available[k] * _OVERALL_WEIGHTS[k] / total_w for k in available)

    # Merge contributing signals for transparency.
    all_contributing: dict[str, float] = {}
    for sub in [trend_sub, momentum_sub, mean_rev_sub]:
        if sub:
            all_contributing.update(sub.contributing)

    return TechnicalScore(
        overall=overall,
        trend=subscores["trend"],
        momentum=subscores["momentum"],
        mean_reversion=subscores["mean_reversion"],
        weights_version=TECH_WEIGHTS_VERSION,
        contributing=all_contributing,
    )
