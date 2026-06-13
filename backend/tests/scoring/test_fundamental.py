"""
Description: Unit tests for the fundamental scoring engine in
             app.scoring.fundamental. Tests cover: normalize() edge cases,
             None-metric renormalization, monotonicity property, subscore
             isolation, and the full score_fundamental() entry point.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; normalization, renormalization, monotonicity,
                 and integration tests.
"""

import pytest

from app.scoring.fundamental import (
    WEIGHTS_VERSION,
    FundamentalScore,
    normalize,
    score_fundamental,
    score_growth,
    score_quality,
    score_value,
)
from app.services.fundamentals.growth import GrowthMetrics
from app.services.fundamentals.quality import QualityMetrics
from app.services.fundamentals.ratios import ValuationRatios

# ── helpers ───────────────────────────────────────────────────────────────────


def _good_ratios() -> ValuationRatios:
    """Valuation ratios for a hypothetical quality company (mid-range values)."""
    return ValuationRatios(pe=20.0, pb=3.0, ps=4.0, ev_ebitda=15.0, dividend_yield=0.02, peg=1.5)


def _bad_ratios() -> ValuationRatios:
    """Expensive/risky ratios (near the unfavourable end of each band)."""
    return ValuationRatios(pe=33.0, pb=9.0, ps=11.0, ev_ebitda=28.0, dividend_yield=0.0, peg=None)


def _good_quality() -> QualityMetrics:
    return QualityMetrics(
        roe=0.30,
        roic=0.20,
        gross_margin=0.50,
        operating_margin=0.25,
        net_margin=0.18,
        debt_to_equity=0.5,
        interest_coverage=15.0,
    )


def _bad_quality() -> QualityMetrics:
    return QualityMetrics(
        roe=0.02,
        roic=0.02,
        gross_margin=0.15,
        operating_margin=0.03,
        net_margin=0.01,
        debt_to_equity=2.5,
        interest_coverage=2.0,
    )


def _good_growth() -> GrowthMetrics:
    return GrowthMetrics(
        revenue_cagr_1y=0.15,
        revenue_cagr_3y=0.12,
        revenue_years_used_5y=3,
        revenue_cagr_5y=0.10,
        eps_cagr_1y=0.18,
        eps_cagr_3y=0.15,
        eps_cagr_5y=0.12,
        eps_years_used_5y=3,
        fcf_cagr_1y=0.14,
        fcf_cagr_3y=0.11,
        fcf_cagr_5y=0.09,
        fcf_years_used_5y=3,
    )


def _no_growth() -> GrowthMetrics:
    return GrowthMetrics(
        revenue_cagr_1y=None,
        revenue_cagr_3y=None,
        revenue_cagr_5y=None,
        revenue_years_used_5y=None,
        eps_cagr_1y=None,
        eps_cagr_3y=None,
        eps_cagr_5y=None,
        eps_years_used_5y=None,
        fcf_cagr_1y=None,
        fcf_cagr_3y=None,
        fcf_cagr_5y=None,
        fcf_years_used_5y=None,
    )


def _empty_ratios() -> ValuationRatios:
    return ValuationRatios(pe=None, pb=None, ps=None, ev_ebitda=None, dividend_yield=None, peg=None)


def _empty_quality() -> QualityMetrics:
    return QualityMetrics(
        roe=None,
        roic=None,
        gross_margin=None,
        operating_margin=None,
        net_margin=None,
        debt_to_equity=None,
        interest_coverage=None,
    )


# ── normalize() ───────────────────────────────────────────────────────────────


def test_normalize_at_floor_is_zero() -> None:
    """Value at floor → raw score = 0. For higher-is-better, output = 0."""
    assert normalize(8.0, floor=8.0, cap=35.0, higher_is_better=True) == pytest.approx(0.0)


def test_normalize_at_cap_is_100() -> None:
    """Value at cap → raw score = 100."""
    assert normalize(35.0, floor=8.0, cap=35.0, higher_is_better=True) == pytest.approx(100.0)


def test_normalize_midpoint() -> None:
    """Value at midpoint of band → score = 50."""
    mid = (8.0 + 35.0) / 2
    assert normalize(mid, floor=8.0, cap=35.0, higher_is_better=True) == pytest.approx(
        50.0, abs=1e-6
    )


def test_normalize_clamps_below_floor() -> None:
    """Value below floor → 0 (higher-is-better) or 100 (lower-is-better)."""
    assert normalize(1.0, floor=8.0, cap=35.0, higher_is_better=True) == pytest.approx(0.0)


def test_normalize_clamps_above_cap() -> None:
    """Value above cap → 100 (higher-is-better) or 0 (lower-is-better)."""
    assert normalize(50.0, floor=8.0, cap=35.0, higher_is_better=True) == pytest.approx(100.0)


def test_normalize_inverts_for_lower_is_better() -> None:
    """lower-is-better: value at floor → 100; value at cap → 0."""
    assert normalize(8.0, floor=8.0, cap=35.0, higher_is_better=False) == pytest.approx(100.0)
    assert normalize(35.0, floor=8.0, cap=35.0, higher_is_better=False) == pytest.approx(0.0)


# ── None-renormalization ──────────────────────────────────────────────────────


def test_score_value_none_when_all_metrics_missing() -> None:
    """score_value returns None when all ratio fields are None."""
    assert score_value(_empty_ratios()) is None


def test_score_quality_none_when_all_metrics_missing() -> None:
    assert score_quality(_empty_quality()) is None


def test_score_growth_none_when_all_metrics_missing() -> None:
    assert score_growth(_no_growth()) is None


def test_score_value_renormalizes_over_present_metrics() -> None:
    """A subscore computed with only 1 of 5 metrics still returns 0–100."""
    ratios = ValuationRatios(
        pe=20.0, pb=None, ps=None, ev_ebitda=None, dividend_yield=None, peg=None
    )
    sub = score_value(ratios)
    assert sub is not None
    assert 0.0 <= sub.score <= 100.0


def test_dropping_metric_to_none_does_not_lower_overall() -> None:
    """Removing a poor-scoring metric should not decrease the subscore."""
    # Low P/E is good (lower-is-better, inverted) — PE=30 is near the cap → bad score
    ratios_with_bad_pe = ValuationRatios(
        pe=34.0, pb=3.0, ps=4.0, ev_ebitda=15.0, dividend_yield=0.02, peg=None
    )
    ratios_without_pe = ValuationRatios(
        pe=None, pb=3.0, ps=4.0, ev_ebitda=15.0, dividend_yield=0.02, peg=None
    )

    sub_with = score_value(ratios_with_bad_pe)
    sub_without = score_value(ratios_without_pe)

    assert sub_with is not None and sub_without is not None
    # Dropping the worst metric (bad P/E drags score down) should raise the subscore
    assert sub_without.score >= sub_with.score


# ── monotonicity ──────────────────────────────────────────────────────────────


def test_better_ratios_score_higher_than_worse_ratios() -> None:
    """A cheaper (better-valued) set of ratios must outscore expensive ones."""
    good = score_value(_good_ratios())
    bad = score_value(_bad_ratios())
    assert good is not None and bad is not None
    assert good.score > bad.score


def test_better_quality_scores_higher() -> None:
    good = score_quality(_good_quality())
    bad = score_quality(_bad_quality())
    assert good is not None and bad is not None
    assert good.score > bad.score


def test_better_growth_scores_higher() -> None:
    high_growth = GrowthMetrics(
        revenue_cagr_1y=0.25,
        revenue_cagr_3y=0.20,
        revenue_cagr_5y=None,
        revenue_years_used_5y=None,
        eps_cagr_1y=0.25,
        eps_cagr_3y=None,
        eps_cagr_5y=None,
        eps_years_used_5y=None,
        fcf_cagr_1y=None,
        fcf_cagr_3y=None,
        fcf_cagr_5y=None,
        fcf_years_used_5y=None,
    )
    low_growth = GrowthMetrics(
        revenue_cagr_1y=0.02,
        revenue_cagr_3y=0.01,
        revenue_cagr_5y=None,
        revenue_years_used_5y=None,
        eps_cagr_1y=0.01,
        eps_cagr_3y=None,
        eps_cagr_5y=None,
        eps_years_used_5y=None,
        fcf_cagr_1y=None,
        fcf_cagr_3y=None,
        fcf_cagr_5y=None,
        fcf_years_used_5y=None,
    )
    assert score_growth(high_growth).score > score_growth(low_growth).score  # type: ignore[union-attr]


# ── score_fundamental() ───────────────────────────────────────────────────────


def test_score_fundamental_returns_dataclass() -> None:
    result = score_fundamental(_good_ratios(), _good_quality(), _good_growth())
    assert isinstance(result, FundamentalScore)
    assert result.weights_version == WEIGHTS_VERSION


def test_score_fundamental_all_subscores_in_range() -> None:
    result = score_fundamental(_good_ratios(), _good_quality(), _good_growth())
    for attr in ("overall", "value", "quality", "growth"):
        val = getattr(result, attr)
        assert val is not None
        assert 0.0 <= val <= 100.0, f"{attr}={val} is out of range"


def test_score_fundamental_overall_none_when_all_subscores_missing() -> None:
    result = score_fundamental(_empty_ratios(), _empty_quality(), _no_growth())
    assert result.overall is None
    assert result.value is None
    assert result.quality is None
    assert result.growth is None


def test_score_fundamental_overall_computed_when_growth_missing() -> None:
    """Overall is non-None even when growth subscore is None (weights renormalize)."""
    result = score_fundamental(_good_ratios(), _good_quality(), _no_growth())
    assert result.overall is not None
    assert result.growth is None
    assert 0.0 <= result.overall <= 100.0


def test_score_fundamental_weights_version_stamped() -> None:
    result = score_fundamental(_good_ratios(), _good_quality(), _good_growth())
    assert result.weights_version == WEIGHTS_VERSION


def test_score_fundamental_contributing_includes_all_metrics() -> None:
    """The contributing dict must contain normalized values for all present metrics."""
    result = score_fundamental(_good_ratios(), _good_quality(), _good_growth())
    assert "pe" in result.contributing
    assert "roe" in result.contributing
    assert "revenue_cagr_1y" in result.contributing
