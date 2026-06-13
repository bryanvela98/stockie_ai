"""
Description: Pure growth-metric (CAGR) calculators for the fundamental analysis module.
             Computes revenue, diluted-EPS, and free-cash-flow CAGRs over 1Y, 3Y,
             and 5Y horizons from a list of annual FinancialStatement ORM rows.
             All functions are side-effect-free: no DB, no network, no mutations.

             yfinance capital_expenditure is stored as a negative value (cash
             outflow convention — see data_providers/README.md Quirk 9).
             FCF = operating_cash_flow + capital_expenditure (adding a negative).

             5Y CAGR degrades gracefully to the longest available span when fewer
             than 6 fiscal years of history exist. The actual span used is reported
             in GrowthMetrics.years_used_* fields so callers can signal uncertainty.

             Returns None (not a crash) for any CAGR when:
               - Available history is too short for the requested horizon.
               - The base-year value is <= 0 (sign-flip makes CAGR meaningless).
               - Required line items (revenue, EPS, OCF) are None in either year.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; GrowthMetrics dataclass, cagr(), and per-metric helpers.
"""

from dataclasses import dataclass

from app.models.financial_statement import FinancialStatement


@dataclass(frozen=True)
class GrowthMetrics:
    """Computed CAGR growth metrics for a single ticker.

    *_1y, *_3y, *_5y are the compound annual growth rates over each horizon,
    expressed as decimal fractions (e.g. 0.08 = 8 % annual growth).
    years_used_* records the actual span used when 5Y degrades to fewer years.
    All fields are Optional; None means insufficient or invalid data.
    """

    revenue_cagr_1y: float | None
    revenue_cagr_3y: float | None
    revenue_cagr_5y: float | None
    revenue_years_used_5y: int | None

    eps_cagr_1y: float | None
    eps_cagr_3y: float | None
    eps_cagr_5y: float | None
    eps_years_used_5y: int | None

    fcf_cagr_1y: float | None
    fcf_cagr_3y: float | None
    fcf_cagr_5y: float | None
    fcf_years_used_5y: int | None


def cagr(values: list[float], years: int) -> float | None:
    """Compute the compound annual growth rate over `years` from an ordered series.

    Args:
        values: Series of annual values ordered **newest-first**. The function
            reads values[0] (end) and values[years] (base, n years ago).
        years: Number of years over which to compute the CAGR. Must be >= 1.

    Returns:
        CAGR as a decimal fraction (e.g. 0.08 = 8 %), or None when:
          - The series does not have enough values for the requested span.
          - The base value (values[years]) is <= 0.
          - Either endpoint is missing (None-safe — caller should filter Nones
            before building `values`).

    Examples:
        >>> cagr([121.0, 100.0], 1)   # 21 % 1-year growth
        0.21
        >>> cagr([133.1, 121.0, 110.0, 100.0], 3)  # ~10 % 3-year CAGR
        0.10...
    """
    if years < 1:
        return None
    if len(values) <= years:
        return None
    end_val = values[0]
    base_val = values[years]
    if base_val <= 0:
        return None
    return float((end_val / base_val) ** (1.0 / years)) - 1.0


def _fcf(stmt: FinancialStatement) -> float | None:
    """Derive free cash flow from a statement row.

    FCF = operating_cash_flow + capital_expenditure.
    capital_expenditure is stored as a negative number (yfinance convention).

    Args:
        stmt: FinancialStatement ORM row.

    Returns:
        FCF as a float, or None if either component is missing.
    """
    if stmt.operating_cash_flow is None or stmt.capital_expenditure is None:
        return None
    return float(int(stmt.operating_cash_flow)) + float(int(stmt.capital_expenditure))


def _best_effort_5y(
    series: list[float],
    max_years: int = 5,
) -> tuple[float | None, int | None]:
    """Compute CAGR over the longest available span up to max_years.

    Args:
        series: Values ordered newest-first.
        max_years: Maximum horizon to attempt.

    Returns:
        Tuple of (cagr_value, actual_years_used). Both None if not computable.
    """
    for n in range(max_years, 0, -1):
        result = cagr(series, n)
        if result is not None:
            return result, n
    return None, None


def compute_growth_metrics(
    statements: list[FinancialStatement],
) -> GrowthMetrics:
    """Compute revenue, EPS, and FCF CAGRs from a list of annual statements.

    Args:
        statements: Annual FinancialStatement rows ordered **newest-first**
            (as returned by FinancialStatementRepository.get_history). At least
            2 rows are needed for 1Y CAGR; 4 for 3Y; 6 for 5Y.

    Returns:
        A GrowthMetrics dataclass. Any horizon for which there is insufficient
        or invalid data will have None for that field.
    """
    rev_series = [float(s.total_revenue) for s in statements if s.total_revenue is not None]
    eps_series = [float(s.eps_diluted) for s in statements if s.eps_diluted is not None]
    fcf_series = [v for s in statements if (v := _fcf(s)) is not None]

    # 5Y best-effort: try 5, 4, 3, … years and record the actual span used
    rev_5y, rev_years = _best_effort_5y(rev_series)
    eps_5y, eps_years = _best_effort_5y(eps_series)
    fcf_5y, fcf_years = _best_effort_5y(fcf_series)

    return GrowthMetrics(
        revenue_cagr_1y=cagr(rev_series, 1),
        revenue_cagr_3y=cagr(rev_series, 3),
        revenue_cagr_5y=rev_5y,
        revenue_years_used_5y=rev_years,
        eps_cagr_1y=cagr(eps_series, 1),
        eps_cagr_3y=cagr(eps_series, 3),
        eps_cagr_5y=eps_5y,
        eps_years_used_5y=eps_years,
        fcf_cagr_1y=cagr(fcf_series, 1),
        fcf_cagr_3y=cagr(fcf_series, 3),
        fcf_cagr_5y=fcf_5y,
        fcf_years_used_5y=fcf_years,
    )
