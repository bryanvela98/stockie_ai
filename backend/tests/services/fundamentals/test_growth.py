"""
Description: Unit tests for the growth-metric (CAGR) calculators in
             app.services.fundamentals.growth. All tests use in-memory
             FinancialStatement instances — no DB, no network.
             Covers: known series for each horizon, short-history fallback,
             negative-base guard, missing-field guard, and FCF derivation.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; cagr(), _fcf(), and compute_growth_metrics() tests.
"""

from decimal import Decimal

import pytest

from app.models.financial_statement import FinancialStatement
from app.services.fundamentals.growth import cagr, compute_growth_metrics

# ── helpers ───────────────────────────────────────────────────────────────────


def _stmt(
    fiscal_year: int,
    revenue: int | None = None,
    eps: float | None = None,
    ocf: int | None = None,
    capex: int | None = None,
) -> FinancialStatement:
    """Build a minimal FinancialStatement in memory (no DB)."""
    return FinancialStatement(  # type: ignore[call-arg]
        id=fiscal_year,
        ticker_id=1,
        fiscal_year=fiscal_year,
        period_type="annual",
        total_revenue=revenue,
        eps_diluted=Decimal(str(eps)) if eps is not None else None,
        operating_cash_flow=ocf,
        capital_expenditure=capex,
    )


def _stmts_revenue(values: list[int]) -> list[FinancialStatement]:
    """Build statements for the given revenue values (newest-first by convention)."""
    return [_stmt(2024 - i, revenue=v) for i, v in enumerate(values)]


# ── cagr() ────────────────────────────────────────────────────────────────────


def test_cagr_1y_known_value() -> None:
    """(121/100)^(1/1) - 1 = 0.21."""
    result = cagr([121.0, 100.0], 1)
    assert result == pytest.approx(0.21, rel=1e-6)


def test_cagr_3y_known_value() -> None:
    """(133.1/100)^(1/3) - 1 ≈ 0.10 (10 % CAGR)."""
    result = cagr([133.1, 121.0, 110.0, 100.0], 3)
    assert result == pytest.approx(0.10, rel=1e-3)


def test_cagr_returns_none_when_series_too_short() -> None:
    """Requesting 3Y CAGR from a 2-element series → None."""
    assert cagr([110.0, 100.0], 3) is None


def test_cagr_returns_none_when_base_is_zero() -> None:
    assert cagr([100.0, 0.0], 1) is None


def test_cagr_returns_none_when_base_is_negative() -> None:
    """Negative base year makes CAGR mathematically undefined."""
    assert cagr([100.0, -50.0], 1) is None


def test_cagr_returns_none_when_years_less_than_one() -> None:
    assert cagr([100.0, 110.0], 0) is None


# ── compute_growth_metrics() ──────────────────────────────────────────────────


def test_growth_metrics_1y_3y_computed_correctly() -> None:
    """With 4 years of revenue data, 1Y and 3Y CAGRs are computable."""
    # Revenues newest-first: 133.1, 121, 110, 100 (10 % CAGR per year)
    stmts = _stmts_revenue([133_100_000, 121_000_000, 110_000_000, 100_000_000])
    result = compute_growth_metrics(stmts)

    assert result.revenue_cagr_1y == pytest.approx(133_100_000 / 121_000_000 - 1, rel=1e-4)
    assert result.revenue_cagr_3y == pytest.approx(0.10, rel=1e-3)


def test_growth_metrics_5y_uses_available_data() -> None:
    """With only 4 years of data, 5Y CAGR degrades to the 3Y span."""
    stmts = _stmts_revenue([133_100_000, 121_000_000, 110_000_000, 100_000_000])
    result = compute_growth_metrics(stmts)

    assert result.revenue_cagr_5y is not None
    assert result.revenue_years_used_5y == 3  # degraded to longest available


def test_growth_metrics_5y_exact_when_six_years_available() -> None:
    """With 6 years of data, 5Y CAGR is computed exactly and years_used=5."""
    stmts = _stmts_revenue([161_051, 146_410, 133_100, 121_000, 110_000, 100_000])
    result = compute_growth_metrics(stmts)

    assert result.revenue_years_used_5y == 5
    assert result.revenue_cagr_5y == pytest.approx(0.10, rel=1e-3)


def test_growth_metrics_eps_cagr_computed() -> None:
    """EPS CAGR: 4 years newest-first, ~10 % growth each year."""
    stmts = [
        _stmt(2024, eps=6.56),
        _stmt(2023, eps=5.97),
        _stmt(2022, eps=6.11),
        _stmt(2021, eps=5.61),
    ]
    result = compute_growth_metrics(stmts)
    assert result.eps_cagr_1y is not None
    assert result.eps_cagr_1y == pytest.approx(6.56 / 5.97 - 1, rel=1e-4)


def test_growth_metrics_fcf_cagr_computed() -> None:
    """FCF = OCF + capex (capex is negative); FCF CAGR is computed correctly."""
    # FCF: 100_000, 90_000, 80_000 (newest first) → ~11.8 % 2Y CAGR
    stmts = [
        _stmt(2024, ocf=110_000, capex=-10_000),  # FCF = 100_000
        _stmt(2023, ocf=100_000, capex=-10_000),  # FCF = 90_000
        _stmt(2022, ocf=90_000, capex=-10_000),  # FCF = 80_000
    ]
    result = compute_growth_metrics(stmts)
    assert result.fcf_cagr_1y is not None
    assert result.fcf_cagr_1y == pytest.approx(100_000 / 90_000 - 1, rel=1e-4)


def test_growth_metrics_all_none_when_no_data() -> None:
    """All CAGRs are None when the statement list is empty or has one row."""
    result = compute_growth_metrics([])
    assert result.revenue_cagr_1y is None
    assert result.eps_cagr_1y is None
    assert result.fcf_cagr_1y is None

    result_one = compute_growth_metrics([_stmt(2024, revenue=100_000)])
    assert result_one.revenue_cagr_1y is None


def test_growth_metrics_none_when_base_revenue_is_zero() -> None:
    """If base-year revenue is 0, CAGR should be None (no division by zero)."""
    stmts = _stmts_revenue([100_000, 0])
    result = compute_growth_metrics(stmts)
    assert result.revenue_cagr_1y is None


def test_growth_metrics_skips_missing_fields() -> None:
    """Statements without a revenue value are skipped when building the series."""
    stmts = [
        _stmt(2024, revenue=110_000),
        _stmt(2023, revenue=None),  # this year is excluded from the series
        _stmt(2022, revenue=100_000),
    ]
    result = compute_growth_metrics(stmts)
    # Series becomes [110_000, 100_000]; only 1Y CAGR is possible
    assert result.revenue_cagr_1y is not None
    assert result.revenue_cagr_3y is None
