"""
Description: Golden-number tests for the complete fundamental pipeline using a
             frozen AAPL fixture (FY2021–FY2024 annual statements + TTM snapshot).
             These tests lock the deterministic contract of the scoring engine:
             any change to normalization bands, weights, or metric functions that
             shifts a subscore by more than ±1.0 on the 0–100 scale will fail
             loudly and require deliberate golden-value updates.

             Fixture source: Apple Inc. public 10-K filings, pinned 2026-06-12.
             See tests/fixtures/aapl_fundamentals.json for the full data and metadata.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; full pipeline golden tests against frozen AAPL data.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.financial_statement import FinancialStatement
from app.models.fundamentals import Fundamentals
from app.scoring.fundamental import WEIGHTS_VERSION, score_fundamental
from app.services.fundamentals.growth import compute_growth_metrics
from app.services.fundamentals.quality import compute_quality_metrics
from app.services.fundamentals.ratios import compute_valuation_ratios

# ── fixture loading ───────────────────────────────────────────────────────────

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "aapl_fundamentals.json"
_SCORE_TOLERANCE = 1.0  # ±1.0 on a 0–100 score


def _load_fixture() -> dict:  # type: ignore[type-arg]
    """Load the frozen AAPL fixture from JSON."""
    return json.loads(_FIXTURE_PATH.read_text())  # type: ignore[no-any-return]


def _build_snapshot(snap: dict) -> Fundamentals:  # type: ignore[type-arg]
    """Construct a Fundamentals ORM instance from the fixture snapshot dict."""
    return Fundamentals(  # type: ignore[call-arg]
        id=1,
        ticker_id=1,
        as_of=date.fromisoformat(snap["as_of"]),
        pe_ratio=Decimal(snap["pe_ratio"]),
        pb_ratio=Decimal(snap["pb_ratio"]),
        ps_ratio=Decimal(snap["ps_ratio"]),
        ev_ebitda=Decimal(snap["ev_ebitda"]),
        eps_ttm=Decimal(str(snap["eps_ttm"])),
        revenue_ttm=snap["revenue_ttm"],
        net_income_ttm=snap["net_income_ttm"],
        roe=Decimal(snap["roe"]),
        debt_to_equity=Decimal(snap["debt_to_equity"]),
        dividend_yield=Decimal(snap["dividend_yield"]),
    )


def _build_statements(stmts: list) -> list[FinancialStatement]:  # type: ignore[type-arg]
    """Construct FinancialStatement ORM instances from the fixture list (newest-first)."""
    return [
        FinancialStatement(  # type: ignore[call-arg]
            id=s["fiscal_year"],
            ticker_id=1,
            fiscal_year=s["fiscal_year"],
            period_type="annual",
            currency="USD",
            total_revenue=s["total_revenue"],
            gross_profit=s["gross_profit"],
            operating_income=s["operating_income"],
            net_income=s["net_income"],
            interest_expense=s["interest_expense"],
            eps_diluted=Decimal(str(s["eps_diluted"])),
            total_assets=s["total_assets"],
            total_equity=s["total_equity"],
            total_debt=s["total_debt"],
            cash_and_equivalents=s["cash_and_equivalents"],
            operating_cash_flow=s["operating_cash_flow"],
            capital_expenditure=s["capital_expenditure"],
            shares_diluted=s["shares_diluted"],
        )
        for s in stmts
    ]


# ── tests ─────────────────────────────────────────────────────────────────────


def test_golden_fixture_exists() -> None:
    """The AAPL fixture file must be committed and readable."""
    assert _FIXTURE_PATH.exists(), f"Missing fixture: {_FIXTURE_PATH}"
    fixture = _load_fixture()
    assert "annual_statements" in fixture
    assert len(fixture["annual_statements"]) >= 3


def test_golden_weights_version_is_current() -> None:
    """Golden scores in the fixture were computed with the current WEIGHTS_VERSION.

    If WEIGHTS_VERSION changes, update the fixture golden_scores and this test.
    """
    # The fixture was generated with v1.0; this test fails if weights change
    # without a deliberate fixture update.
    assert WEIGHTS_VERSION == "v1.0", (
        f"WEIGHTS_VERSION changed to {WEIGHTS_VERSION!r}. "
        "Update tests/fixtures/aapl_fundamentals.json golden_scores."
    )


def test_golden_pipeline_value_subscore() -> None:
    """Value subscore for AAPL (expensive stock) should be near 8.3 on the 0–100 scale."""
    fixture = _load_fixture()
    snap = _build_snapshot(fixture["snapshot"])
    stmts = _build_statements(fixture["annual_statements"])

    ratios = compute_valuation_ratios(snap)
    quality = compute_quality_metrics(stmts[0], snapshot=snap)
    growth = compute_growth_metrics(stmts)
    result = score_fundamental(ratios, quality, growth)

    expected = fixture["golden_scores"]["value"]
    assert result.value is not None
    assert result.value == pytest.approx(expected, abs=_SCORE_TOLERANCE), (
        f"Value subscore {result.value:.2f} differs from golden {expected}. "
        "Did normalization bands or weights change?"
    )


def test_golden_pipeline_quality_subscore() -> None:
    """Quality subscore for AAPL (exceptional profitability) should be near 86.5."""
    fixture = _load_fixture()
    snap = _build_snapshot(fixture["snapshot"])
    stmts = _build_statements(fixture["annual_statements"])

    ratios = compute_valuation_ratios(snap)
    quality = compute_quality_metrics(stmts[0], snapshot=snap)
    growth = compute_growth_metrics(stmts)
    result = score_fundamental(ratios, quality, growth)

    expected = fixture["golden_scores"]["quality"]
    assert result.quality is not None
    assert result.quality == pytest.approx(expected, abs=_SCORE_TOLERANCE)


def test_golden_pipeline_growth_subscore() -> None:
    """Growth subscore for AAPL (flat revenue FY2022–2024) should be near 25.7."""
    fixture = _load_fixture()
    snap = _build_snapshot(fixture["snapshot"])
    stmts = _build_statements(fixture["annual_statements"])

    ratios = compute_valuation_ratios(snap)
    quality = compute_quality_metrics(stmts[0], snapshot=snap)
    growth = compute_growth_metrics(stmts)
    result = score_fundamental(ratios, quality, growth)

    expected = fixture["golden_scores"]["growth"]
    assert result.growth is not None
    assert result.growth == pytest.approx(expected, abs=_SCORE_TOLERANCE)


def test_golden_pipeline_overall_score() -> None:
    """Overall score for AAPL should be near 40.9 (expensive quality compounder)."""
    fixture = _load_fixture()
    snap = _build_snapshot(fixture["snapshot"])
    stmts = _build_statements(fixture["annual_statements"])

    ratios = compute_valuation_ratios(snap)
    quality = compute_quality_metrics(stmts[0], snapshot=snap)
    growth = compute_growth_metrics(stmts)
    result = score_fundamental(ratios, quality, growth)

    expected = fixture["golden_scores"]["overall"]
    assert result.overall is not None
    assert result.overall == pytest.approx(expected, abs=_SCORE_TOLERANCE)


def test_golden_pipeline_weights_version_stamped() -> None:
    """FundamentalScore must carry the current WEIGHTS_VERSION."""
    fixture = _load_fixture()
    snap = _build_snapshot(fixture["snapshot"])
    stmts = _build_statements(fixture["annual_statements"])

    ratios = compute_valuation_ratios(snap)
    quality = compute_quality_metrics(stmts[0], snapshot=snap)
    growth = compute_growth_metrics(stmts)
    result = score_fundamental(ratios, quality, growth)

    assert result.weights_version == WEIGHTS_VERSION


def test_golden_pipeline_growth_metrics_from_fixture() -> None:
    """Revenue CAGR over 1Y from the AAPL fixture should be ~2 % (flat growth)."""
    fixture = _load_fixture()
    stmts = _build_statements(fixture["annual_statements"])
    growth = compute_growth_metrics(stmts)

    # FY2024 / FY2023 revenue ≈ 391_035 / 383_285 → ~2 %
    expected_1y = 391_035_000_000 / 383_285_000_000 - 1
    assert growth.revenue_cagr_1y is not None
    assert growth.revenue_cagr_1y == pytest.approx(expected_1y, rel=1e-4)

    # With 4 years of data, 3Y CAGR is computable; 5Y falls back to 3Y
    assert growth.revenue_cagr_3y is not None
    assert growth.revenue_years_used_5y == 3
