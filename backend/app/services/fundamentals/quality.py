"""
Description: Pure quality-metric calculators for the fundamental analysis module.
             Computes profitability, safety, and efficiency metrics from a
             FinancialStatement ORM row (and optionally a Fundamentals snapshot).
             All functions are side-effect-free: no DB, no network, no mutations.
             Missing or non-positive denominators always return None rather than
             raising; zero-denominator divisions produce None, not inf or NaN.

             NOPAT approximation: operating_income × (1 − DEFAULT_TAX_RATE).
             US statutory corporate rate is 21 %. We use this as the default for
             MVP because company-specific effective tax rates require multi-period
             tax-provision data that is unreliable across yfinance label variants.
             The constant is named and documented so it can be overridden per
             ticker in a future sprint.

             debtToEquity from yfinance is stored as a percentage (e.g. 150.0 =
             150 %). When reading debt_to_equity from the Fundamentals snapshot
             we divide by 100 to obtain the standard ratio. When computing from
             FinancialStatement line items we use total_debt / total_equity directly.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; QualityMetrics dataclass and calculator functions.
"""

from dataclasses import dataclass

from app.models.financial_statement import FinancialStatement
from app.models.fundamentals import Fundamentals

# US statutory corporate income-tax rate — used to approximate NOPAT.
# Effective rates vary by company; 21 % is the MVP constant.
DEFAULT_TAX_RATE: float = 0.21


@dataclass(frozen=True)
class QualityMetrics:
    """Computed quality metrics for a single ticker from one fiscal year.

    All fields are Optional; coverage varies by asset type and by whether the
    required statement line items are present.
    """

    roe: float | None
    roic: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    debt_to_equity: float | None
    interest_coverage: float | None


def roe(snapshot: Fundamentals) -> float | None:
    """Return ROE directly from the fundamentals snapshot (yfinance provides it).

    The snapshot value is a decimal fraction (e.g. 1.47 = 147 %).

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        Return on equity as a float, or None if not available.
    """
    if snapshot.roe is None:
        return None
    return float(snapshot.roe)


def roic(stmt: FinancialStatement, tax_rate: float = DEFAULT_TAX_RATE) -> float | None:
    """Compute Return on Invested Capital (ROIC).

    ROIC = NOPAT / Invested Capital
    NOPAT = operating_income × (1 − tax_rate)
    Invested Capital = total_debt + total_equity − cash_and_equivalents

    A negative or zero invested capital produces None (often means the company
    is cash-rich beyond its debt + equity, which makes ROIC undefined).

    Args:
        stmt: Annual FinancialStatement ORM row containing balance-sheet and
              income-statement line items.
        tax_rate: Effective corporate income-tax rate. Defaults to DEFAULT_TAX_RATE.

    Returns:
        ROIC as a float, or None if required inputs are missing or invalid.
    """
    if stmt.operating_income is None or stmt.total_debt is None or stmt.total_equity is None:
        return None

    nopat = stmt.operating_income * (1.0 - tax_rate)
    invested_capital = stmt.total_debt + stmt.total_equity - (stmt.cash_and_equivalents or 0)
    if invested_capital <= 0:
        return None

    return nopat / invested_capital


def gross_margin(stmt: FinancialStatement) -> float | None:
    """Compute gross margin: gross_profit / total_revenue.

    Args:
        stmt: Annual FinancialStatement ORM row.

    Returns:
        Gross margin as a decimal fraction (e.g. 0.43 = 43 %), or None if
        total_revenue is missing or non-positive.
    """
    if stmt.total_revenue is None or stmt.total_revenue <= 0:
        return None
    if stmt.gross_profit is None:
        return None
    return stmt.gross_profit / stmt.total_revenue


def operating_margin(stmt: FinancialStatement) -> float | None:
    """Compute operating margin: operating_income / total_revenue.

    Args:
        stmt: Annual FinancialStatement ORM row.

    Returns:
        Operating margin as a decimal fraction, or None if inputs are missing
        or revenue is non-positive.
    """
    if stmt.total_revenue is None or stmt.total_revenue <= 0:
        return None
    if stmt.operating_income is None:
        return None
    return stmt.operating_income / stmt.total_revenue


def net_margin(stmt: FinancialStatement) -> float | None:
    """Compute net margin: net_income / total_revenue.

    Args:
        stmt: Annual FinancialStatement ORM row.

    Returns:
        Net margin as a decimal fraction, or None if inputs are missing or
        revenue is non-positive.
    """
    if stmt.total_revenue is None or stmt.total_revenue <= 0:
        return None
    if stmt.net_income is None:
        return None
    return stmt.net_income / stmt.total_revenue


def debt_to_equity(
    stmt: FinancialStatement | None = None,
    snapshot: Fundamentals | None = None,
) -> float | None:
    """Return the debt-to-equity ratio, preferring statement line items over the snapshot.

    When a FinancialStatement is provided, computes total_debt / total_equity.
    When only a Fundamentals snapshot is available, divides the stored percentage
    value by 100 to obtain the standard ratio (yfinance stores D/E as a percentage).

    Args:
        stmt: Annual FinancialStatement ORM row. Preferred source.
        snapshot: Fundamentals ORM row. Used as fallback when stmt is None.

    Returns:
        Debt-to-equity ratio as a float, or None if required inputs are missing
        or equity is non-positive.
    """
    if stmt is not None:
        if stmt.total_equity is None or stmt.total_equity <= 0:
            return None
        if stmt.total_debt is None:
            return None
        return stmt.total_debt / stmt.total_equity

    if snapshot is not None and snapshot.debt_to_equity is not None:
        # yfinance stores D/E as a percentage (Quirk 3 in data_providers/README.md)
        return float(snapshot.debt_to_equity) / 100.0

    return None


def interest_coverage(stmt: FinancialStatement) -> float | None:
    """Compute interest coverage: operating_income / interest_expense.

    A positive interest_expense is expected (it is a cost). If the stored value
    is negative (some providers flip the sign), we take its absolute value.
    Returns None when interest_expense is zero or missing (no debt to cover).

    Args:
        stmt: Annual FinancialStatement ORM row.

    Returns:
        Interest coverage ratio as a float, or None if inputs are missing or
        interest_expense is zero.
    """
    if stmt.operating_income is None or stmt.interest_expense is None:
        return None
    abs_interest = abs(stmt.interest_expense)
    if abs_interest == 0:
        return None
    return stmt.operating_income / abs_interest


def compute_quality_metrics(
    stmt: FinancialStatement,
    snapshot: Fundamentals | None = None,
    tax_rate: float = DEFAULT_TAX_RATE,
) -> QualityMetrics:
    """Compute all quality metrics for a ticker from one annual statement.

    ROE is sourced from the snapshot when available (yfinance provides it
    pre-computed). All other metrics derive from the FinancialStatement row.

    Args:
        stmt: Annual FinancialStatement ORM row.
        snapshot: Latest Fundamentals snapshot. Used for ROE and as D/E fallback.
        tax_rate: Effective corporate income-tax rate for ROIC. Defaults to
            DEFAULT_TAX_RATE (21 %).

    Returns:
        A QualityMetrics dataclass with all computed metrics.
    """
    _roe = roe(snapshot) if snapshot is not None else None
    _de = debt_to_equity(stmt=stmt, snapshot=snapshot)

    return QualityMetrics(
        roe=_roe,
        roic=roic(stmt, tax_rate),
        gross_margin=gross_margin(stmt),
        operating_margin=operating_margin(stmt),
        net_margin=net_margin(stmt),
        debt_to_equity=_de,
        interest_coverage=interest_coverage(stmt),
    )
