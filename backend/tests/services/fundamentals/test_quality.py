"""
Description: Unit tests for the quality-metric calculators in
             app.services.fundamentals.quality. All tests build minimal ORM
             instances in memory — no DB, no network. Covers happy paths, a
             fully-worked golden statement, and all None-guard branches.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; golden-statement tests and None-guard branches.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.financial_statement import FinancialStatement
from app.models.fundamentals import Fundamentals
from app.services.fundamentals.quality import (
    DEFAULT_TAX_RATE,
    QualityMetrics,
    compute_quality_metrics,
    debt_to_equity,
    gross_margin,
    interest_coverage,
    net_margin,
    operating_margin,
    roe,
    roic,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _stmt(**overrides: object) -> FinancialStatement:
    """Build a minimal FinancialStatement ORM instance without hitting the DB."""
    defaults: dict[str, object] = {
        "id": 1,
        "ticker_id": 1,
        "fiscal_year": 2024,
        "period_type": "annual",
        # Loosely modelled on AAPL FY2024 (rounded for simplicity)
        "total_revenue": 391_035_000_000,
        "gross_profit": 169_148_000_000,
        "operating_income": 69_144_000_000,
        "net_income": 93_736_000_000,
        "interest_expense": 3_930_000_000,
        "eps_diluted": Decimal("6.08"),
        "total_assets": 364_980_000_000,
        "total_equity": 56_950_000_000,
        "total_debt": 96_630_000_000,
        "cash_and_equivalents": 65_171_000_000,
        "operating_cash_flow": 118_254_000_000,
        "capital_expenditure": -9_447_000_000,
        "shares_diluted": 15_408_000_000,
        "currency": "USD",
    }
    defaults.update(overrides)
    return FinancialStatement(**defaults)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> Fundamentals:
    """Build a minimal Fundamentals ORM instance without hitting the DB."""
    defaults: dict[str, object] = {
        "id": 1,
        "ticker_id": 1,
        "as_of": date(2024, 9, 28),
        "roe": Decimal("1.47"),
        "debt_to_equity": Decimal("150.0"),
    }
    defaults.update(overrides)
    return Fundamentals(**defaults)  # type: ignore[arg-type]


# ── roe ───────────────────────────────────────────────────────────────────────


def test_roe_from_snapshot() -> None:
    """ROE is extracted from the snapshot's roe column."""
    snap = _snapshot(roe=Decimal("1.47"))
    assert roe(snap) == pytest.approx(1.47)


def test_roe_none_when_missing() -> None:
    snap = _snapshot(roe=None)
    assert roe(snap) is None


# ── roic ──────────────────────────────────────────────────────────────────────


def test_roic_golden_computation() -> None:
    """ROIC = NOPAT / Invested Capital.

    Golden inputs (rounded AAPL FY2024 approximations):
      operating_income = 69_144_000_000
      tax_rate         = 0.21
      NOPAT            = 69_144_000_000 × 0.79 = 54_623_760_000
      total_debt       = 96_630_000_000
      total_equity     = 56_950_000_000
      cash             = 65_171_000_000
      invested_capital = 96_630 + 56_950 − 65_171 = 88_409_000_000
      ROIC             ≈ 54_623_760_000 / 88_409_000_000 ≈ 0.6179
    """
    stmt = _stmt()
    result = roic(stmt)
    assert result is not None
    assert result == pytest.approx(
        69_144_000_000
        * (1 - DEFAULT_TAX_RATE)
        / (96_630_000_000 + 56_950_000_000 - 65_171_000_000),
        rel=1e-4,
    )


def test_roic_none_when_operating_income_missing() -> None:
    assert roic(_stmt(operating_income=None)) is None


def test_roic_none_when_total_debt_missing() -> None:
    assert roic(_stmt(total_debt=None)) is None


def test_roic_none_when_total_equity_missing() -> None:
    assert roic(_stmt(total_equity=None)) is None


def test_roic_none_when_invested_capital_nonpositive() -> None:
    """A company whose cash exceeds debt + equity has undefined ROIC."""
    stmt = _stmt(total_debt=10, total_equity=10, cash_and_equivalents=100)
    assert roic(stmt) is None


# ── margins ───────────────────────────────────────────────────────────────────


def test_gross_margin_golden() -> None:
    """gross_profit / total_revenue = 169_148 / 391_035 ≈ 0.4326."""
    stmt = _stmt()
    result = gross_margin(stmt)
    assert result is not None
    assert result == pytest.approx(169_148_000_000 / 391_035_000_000, rel=1e-4)


def test_gross_margin_none_when_revenue_missing() -> None:
    assert gross_margin(_stmt(total_revenue=None)) is None


def test_gross_margin_none_when_revenue_zero() -> None:
    assert gross_margin(_stmt(total_revenue=0)) is None


def test_gross_margin_none_when_gross_profit_missing() -> None:
    assert gross_margin(_stmt(gross_profit=None)) is None


def test_operating_margin_golden() -> None:
    stmt = _stmt()
    result = operating_margin(stmt)
    assert result is not None
    assert result == pytest.approx(69_144_000_000 / 391_035_000_000, rel=1e-4)


def test_operating_margin_none_when_revenue_missing() -> None:
    assert operating_margin(_stmt(total_revenue=None)) is None


def test_net_margin_golden() -> None:
    stmt = _stmt()
    result = net_margin(stmt)
    assert result is not None
    assert result == pytest.approx(93_736_000_000 / 391_035_000_000, rel=1e-4)


def test_net_margin_none_when_net_income_missing() -> None:
    assert net_margin(_stmt(net_income=None)) is None


# ── debt_to_equity ────────────────────────────────────────────────────────────


def test_debt_to_equity_from_statement() -> None:
    """Prefers statement line items: total_debt / total_equity."""
    stmt = _stmt(total_debt=96_630_000_000, total_equity=56_950_000_000)
    result = debt_to_equity(stmt=stmt)
    assert result is not None
    assert result == pytest.approx(96_630_000_000 / 56_950_000_000, rel=1e-4)


def test_debt_to_equity_falls_back_to_snapshot_percentage() -> None:
    """When stmt is None, uses snapshot D/E (percentage) and divides by 100."""
    snap = _snapshot(debt_to_equity=Decimal("150.0"))
    result = debt_to_equity(snapshot=snap)
    assert result == pytest.approx(1.5)


def test_debt_to_equity_none_when_equity_zero() -> None:
    assert debt_to_equity(stmt=_stmt(total_equity=0)) is None


def test_debt_to_equity_none_when_equity_negative() -> None:
    assert debt_to_equity(stmt=_stmt(total_equity=-1)) is None


def test_debt_to_equity_none_when_debt_missing() -> None:
    assert debt_to_equity(stmt=_stmt(total_debt=None)) is None


# ── interest_coverage ─────────────────────────────────────────────────────────


def test_interest_coverage_golden() -> None:
    """operating_income / abs(interest_expense) = 69_144 / 3_930 ≈ 17.59."""
    stmt = _stmt()
    result = interest_coverage(stmt)
    assert result is not None
    assert result == pytest.approx(69_144_000_000 / 3_930_000_000, rel=1e-4)


def test_interest_coverage_handles_negative_interest_sign() -> None:
    """Some providers store interest_expense as a negative number; we abs() it."""
    stmt = _stmt(interest_expense=-3_930_000_000)
    result = interest_coverage(stmt)
    assert result is not None
    assert result == pytest.approx(69_144_000_000 / 3_930_000_000, rel=1e-4)


def test_interest_coverage_none_when_interest_missing() -> None:
    assert interest_coverage(_stmt(interest_expense=None)) is None


def test_interest_coverage_none_when_interest_zero() -> None:
    assert interest_coverage(_stmt(interest_expense=0)) is None


# ── compute_quality_metrics ───────────────────────────────────────────────────


def test_compute_quality_metrics_returns_dataclass() -> None:
    """compute_quality_metrics returns a fully-populated QualityMetrics."""
    stmt = _stmt()
    snap = _snapshot()
    result = compute_quality_metrics(stmt, snapshot=snap)

    assert isinstance(result, QualityMetrics)
    assert result.roe == pytest.approx(1.47)
    assert result.roic is not None and result.roic > 0
    assert result.gross_margin is not None and 0 < result.gross_margin < 1
    assert result.operating_margin is not None and 0 < result.operating_margin < 1
    assert result.net_margin is not None and 0 < result.net_margin < 1
    assert result.debt_to_equity is not None and result.debt_to_equity > 0
    assert result.interest_coverage is not None and result.interest_coverage > 1


def test_compute_quality_metrics_all_none_when_no_data() -> None:
    """All metrics are None when statement has no data and no snapshot is given."""
    empty_stmt = _stmt(
        total_revenue=None,
        gross_profit=None,
        operating_income=None,
        net_income=None,
        interest_expense=None,
        total_equity=None,
        total_debt=None,
        cash_and_equivalents=None,
    )
    result = compute_quality_metrics(empty_stmt)

    assert result.roe is None
    assert result.roic is None
    assert result.gross_margin is None
    assert result.operating_margin is None
    assert result.net_margin is None
    assert result.interest_coverage is None
