"""
Description: Fundamental scoring engine for Stockie AI.
             Converts ValuationRatios, QualityMetrics, and GrowthMetrics into
             three 0–100 subscores (Value, Quality, Growth) and an overall
             FundamentalScore via a deterministic, documented weighting scheme.

             DESIGN PRINCIPLES:
             - Normalization is piecewise-linear: each metric has a (floor, cap)
               band. A value at or below the floor scores 0; at or above the cap
               scores 100; linearly interpolated between them.
             - "Lower is better" metrics (P/E, D/E, etc.) are inverted after
               normalization so the scale is always "higher = better".
             - None metrics are excluded from their subscore; the remaining
               weights are renormalized. A subscore with no inputs is None, not 0.
             - WEIGHTS_VERSION is stamped on every FundamentalScore so future
               re-weightings are traceable (supports Sprint 6 backtesting).

             NORMALIZATION BANDS (MVP — US equities universe):
             These are intentionally conservative, sector-agnostic ranges chosen
             to cover the S&P 500 universe. Sector-relative normalization is
             deferred to post-MVP.

             VALUE BANDS (lower P/E → better → inverted):
               pe:           floor=8,   cap=35    (typical US equity range)
               pb:           floor=0.5, cap=10    (book-value range)
               ps:           floor=0.5, cap=12    (sales multiple range)
               ev_ebitda:    floor=5,   cap=30    (enterprise-value range)
               dividend_yield: floor=0, cap=0.06  (0–6 % yield; higher is better)

             QUALITY BANDS (mostly higher-is-better):
               roe:          floor=0,   cap=0.40  (0–40 % ROE)
               roic:         floor=0,   cap=0.30  (0–30 % ROIC)
               gross_margin: floor=0.1, cap=0.70  (10–70 % gross margin)
               operating_margin: floor=0, cap=0.35 (0–35 % operating margin)
               net_margin:   floor=0,   cap=0.25  (0–25 % net margin)
               debt_to_equity: floor=0, cap=3.0   (0–3× D/E; lower is better)
               interest_coverage: floor=1, cap=20 (1–20× coverage; higher better)

             GROWTH BANDS (all higher-is-better):
               revenue_cagr: floor=-0.05, cap=0.30  (−5 % to +30 % CAGR)
               eps_cagr:     floor=-0.10, cap=0.35  (−10 % to +35 % CAGR)
               fcf_cagr:     floor=-0.10, cap=0.30  (−10 % to +30 % CAGR)

             SUBSCORE WEIGHTS:
               Value:   pe=25%, pb=15%, ps=15%, ev_ebitda=25%, div_yield=20%
               Quality: roe=20%, roic=20%, gross_margin=15%, op_margin=15%,
                        net_margin=10%, debt_to_equity=10%, interest_coverage=10%
               Growth:  revenue_1y=20%, revenue_3y=20%, eps_1y=20%, eps_3y=20%,
                        fcf_1y=10%, fcf_3y=10%

             OVERALL WEIGHTS:
               Value=35%, Quality=35%, Growth=30%

Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; FundamentalScore, normalize(), subscore functions,
                 and score_fundamental() entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.fundamentals.growth import GrowthMetrics
from app.services.fundamentals.quality import QualityMetrics
from app.services.fundamentals.ratios import ValuationRatios

# ── version ───────────────────────────────────────────────────────────────────

# Increment this string whenever any band or weight changes so that stored
# scores can be compared against the version that produced them.
WEIGHTS_VERSION = "v1.0"

# ── normalization bands ───────────────────────────────────────────────────────
# Each entry: (floor, cap, higher_is_better)
# "higher_is_better=False" means the metric is inverted after normalization.

_VALUE_BANDS: dict[str, tuple[float, float, bool]] = {
    # Lower multiples → better value → inverted
    "pe": (8.0, 35.0, False),
    "pb": (0.5, 10.0, False),
    "ps": (0.5, 12.0, False),
    "ev_ebitda": (5.0, 30.0, False),
    # Higher yield → more income → not inverted
    "dividend_yield": (0.0, 0.06, True),
}

_QUALITY_BANDS: dict[str, tuple[float, float, bool]] = {
    "roe": (0.0, 0.40, True),
    "roic": (0.0, 0.30, True),
    "gross_margin": (0.10, 0.70, True),
    "operating_margin": (0.0, 0.35, True),
    "net_margin": (0.0, 0.25, True),
    "debt_to_equity": (0.0, 3.0, False),  # lower D/E → safer → inverted
    "interest_coverage": (1.0, 20.0, True),
}

_GROWTH_BANDS: dict[str, tuple[float, float, bool]] = {
    "revenue_cagr_1y": (-0.05, 0.30, True),
    "revenue_cagr_3y": (-0.05, 0.30, True),
    "eps_cagr_1y": (-0.10, 0.35, True),
    "eps_cagr_3y": (-0.10, 0.35, True),
    "fcf_cagr_1y": (-0.10, 0.30, True),
    "fcf_cagr_3y": (-0.10, 0.30, True),
}

# ── subscore weights ──────────────────────────────────────────────────────────
# Weights must sum to 1.0 within each subscore group.

_VALUE_WEIGHTS: dict[str, float] = {
    "pe": 0.25,
    "pb": 0.15,
    "ps": 0.15,
    "ev_ebitda": 0.25,
    "dividend_yield": 0.20,
}

_QUALITY_WEIGHTS: dict[str, float] = {
    "roe": 0.20,
    "roic": 0.20,
    "gross_margin": 0.15,
    "operating_margin": 0.15,
    "net_margin": 0.10,
    "debt_to_equity": 0.10,
    "interest_coverage": 0.10,
}

_GROWTH_WEIGHTS: dict[str, float] = {
    "revenue_cagr_1y": 0.20,
    "revenue_cagr_3y": 0.20,
    "eps_cagr_1y": 0.20,
    "eps_cagr_3y": 0.20,
    "fcf_cagr_1y": 0.10,
    "fcf_cagr_3y": 0.10,
}

# Overall weights for combining the three subscores
_OVERALL_WEIGHTS: dict[str, float] = {
    "value": 0.35,
    "quality": 0.35,
    "growth": 0.30,
}

# ── output types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Subscore:
    """A single 0–100 subscore with the contributing metric values for transparency."""

    score: float
    contributing: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class FundamentalScore:
    """Complete fundamental score for a single ticker snapshot.

    overall, value, quality, and growth are 0–100. Any subscore with no
    available inputs will be None (not 0). The overall score is None when
    all three subscores are None.
    """

    overall: float | None
    value: float | None
    quality: float | None
    growth: float | None
    weights_version: str
    # Raw metric values included for UI transparency and debugging
    contributing: dict[str, float] = field(default_factory=dict)


# ── normalization ─────────────────────────────────────────────────────────────


def normalize(value: float, floor: float, cap: float, higher_is_better: bool) -> float:
    """Map a raw metric value to a 0–100 score using a piecewise-linear band.

    Values at or below floor map to 0 (before inversion for lower-is-better).
    Values at or above cap map to 100. Values between floor and cap are linearly
    interpolated.

    For lower-is-better metrics (higher_is_better=False) the result is inverted:
    100 − score, so a low raw value produces a high score.

    Args:
        value: Raw metric value to normalize.
        floor: Lower bound of the band. Raw values ≤ floor → raw score = 0.
        cap: Upper bound of the band. Raw values ≥ cap → raw score = 100.
        higher_is_better: When False, the normalized score is inverted (100 − score).

    Returns:
        Normalized score in [0, 100].
    """
    if cap == floor:
        raw = 100.0 if value >= cap else 0.0
    else:
        raw = (value - floor) / (cap - floor) * 100.0
        raw = max(0.0, min(100.0, raw))

    return (100.0 - raw) if not higher_is_better else raw


# ── subscore helpers ──────────────────────────────────────────────────────────


def _weighted_subscore(
    metric_values: dict[str, float | None],
    bands: dict[str, tuple[float, float, bool]],
    weights: dict[str, float],
) -> Subscore | None:
    """Compute a weighted subscore from a set of metrics, bands, and weights.

    None metrics are excluded and the surviving weights are renormalized so they
    still sum to 1.0. If all metrics are None, returns None.

    Args:
        metric_values: Dict of metric name → raw value (or None if unavailable).
        bands: Dict of metric name → (floor, cap, higher_is_better).
        weights: Dict of metric name → raw weight (should sum to 1.0).

    Returns:
        A Subscore with the weighted average score in [0, 100] and the
        contributing normalized values, or None if no metrics are available.
    """
    present: dict[str, float] = {}
    total_weight = 0.0

    for name, raw_value in metric_values.items():
        if raw_value is None:
            continue
        floor, cap, higher_is_better = bands[name]
        normalized = normalize(raw_value, floor, cap, higher_is_better)
        present[name] = normalized
        total_weight += weights[name]

    if not present or total_weight == 0.0:
        return None

    score = sum(present[name] * weights[name] / total_weight for name in present)
    return Subscore(score=score, contributing=present)


# ── subscore functions ────────────────────────────────────────────────────────


def score_value(ratios: ValuationRatios) -> Subscore | None:
    """Compute the Value subscore (0–100) from valuation ratios.

    Args:
        ratios: ValuationRatios dataclass from services.fundamentals.ratios.

    Returns:
        A Subscore, or None if no valuation metrics are available.
    """
    return _weighted_subscore(
        {
            "pe": ratios.pe,
            "pb": ratios.pb,
            "ps": ratios.ps,
            "ev_ebitda": ratios.ev_ebitda,
            "dividend_yield": ratios.dividend_yield,
        },
        _VALUE_BANDS,
        _VALUE_WEIGHTS,
    )


def score_quality(quality: QualityMetrics) -> Subscore | None:
    """Compute the Quality subscore (0–100) from quality metrics.

    Args:
        quality: QualityMetrics dataclass from services.fundamentals.quality.

    Returns:
        A Subscore, or None if no quality metrics are available.
    """
    return _weighted_subscore(
        {
            "roe": quality.roe,
            "roic": quality.roic,
            "gross_margin": quality.gross_margin,
            "operating_margin": quality.operating_margin,
            "net_margin": quality.net_margin,
            "debt_to_equity": quality.debt_to_equity,
            "interest_coverage": quality.interest_coverage,
        },
        _QUALITY_BANDS,
        _QUALITY_WEIGHTS,
    )


def score_growth(growth: GrowthMetrics) -> Subscore | None:
    """Compute the Growth subscore (0–100) from CAGR metrics.

    Args:
        growth: GrowthMetrics dataclass from services.fundamentals.growth.

    Returns:
        A Subscore, or None if no growth metrics are available.
    """
    return _weighted_subscore(
        {
            "revenue_cagr_1y": growth.revenue_cagr_1y,
            "revenue_cagr_3y": growth.revenue_cagr_3y,
            "eps_cagr_1y": growth.eps_cagr_1y,
            "eps_cagr_3y": growth.eps_cagr_3y,
            "fcf_cagr_1y": growth.fcf_cagr_1y,
            "fcf_cagr_3y": growth.fcf_cagr_3y,
        },
        _GROWTH_BANDS,
        _GROWTH_WEIGHTS,
    )


# ── entry point ───────────────────────────────────────────────────────────────


def score_fundamental(
    ratios: ValuationRatios,
    quality: QualityMetrics,
    growth: GrowthMetrics,
) -> FundamentalScore:
    """Compute the complete FundamentalScore from all three metric groups.

    The overall score is a weighted mean of the three subscores. A subscore
    that is None (no data) is excluded and the overall weights are renormalized
    over the present subscores.

    Args:
        ratios: Valuation ratios from services.fundamentals.ratios.
        quality: Quality metrics from services.fundamentals.quality.
        growth: Growth metrics from services.fundamentals.growth.

    Returns:
        A FundamentalScore with overall, value, quality, growth in [0, 100]
        and WEIGHTS_VERSION stamped. Any subscore with no inputs will be None.
    """
    v_sub = score_value(ratios)
    q_sub = score_quality(quality)
    g_sub = score_growth(growth)

    subscore_values: dict[str, float | None] = {
        "value": v_sub.score if v_sub is not None else None,
        "quality": q_sub.score if q_sub is not None else None,
        "growth": g_sub.score if g_sub is not None else None,
    }

    # Compute overall over present subscores only
    present = {k: v for k, v in subscore_values.items() if v is not None}
    if present:
        total_w = sum(_OVERALL_WEIGHTS[k] for k in present)
        overall: float | None = sum(present[k] * _OVERALL_WEIGHTS[k] / total_w for k in present)
    else:
        overall = None

    # Merge all contributing normalized values for transparency
    all_contributing: dict[str, float] = {}
    for sub in (v_sub, q_sub, g_sub):
        if sub is not None:
            all_contributing.update(sub.contributing)

    return FundamentalScore(
        overall=overall,
        value=v_sub.score if v_sub is not None else None,
        quality=q_sub.score if q_sub is not None else None,
        growth=g_sub.score if g_sub is not None else None,
        weights_version=WEIGHTS_VERSION,
        contributing=all_contributing,
    )
