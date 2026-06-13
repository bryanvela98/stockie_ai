"""
Description: Pure valuation-ratio calculators for the fundamental analysis module.
             All functions accept a Fundamentals ORM snapshot (or individual
             numeric inputs) and return a ValuationRatios dataclass.
             No I/O, no database access — fully unit-testable in isolation.
             Missing or non-positive denominators always return None rather than
             raising, because data coverage varies by asset type and provider.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; ValuationRatios dataclass and calculator functions.
"""

from dataclasses import dataclass

from app.models.fundamentals import Fundamentals


@dataclass(frozen=True)
class ValuationRatios:
    """Computed valuation ratios for a single ticker snapshot.

    All fields are Optional because coverage varies by asset type (ETFs lack
    earnings-based ratios) and because some ratios require positive denominators.
    """

    pe: float | None
    pb: float | None
    ps: float | None
    ev_ebitda: float | None
    dividend_yield: float | None
    peg: float | None


def pe(snapshot: Fundamentals) -> float | None:
    """Return the trailing price-to-earnings ratio from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        P/E ratio as a float, or None if not available in the snapshot.
    """
    if snapshot.pe_ratio is None:
        return None
    return float(snapshot.pe_ratio)


def pb(snapshot: Fundamentals) -> float | None:
    """Return the price-to-book ratio from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        P/B ratio as a float, or None if not available in the snapshot.
    """
    if snapshot.pb_ratio is None:
        return None
    return float(snapshot.pb_ratio)


def ps(snapshot: Fundamentals) -> float | None:
    """Return the price-to-sales ratio from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        P/S ratio as a float, or None if not available in the snapshot.
    """
    if snapshot.ps_ratio is None:
        return None
    return float(snapshot.ps_ratio)


def ev_ebitda(snapshot: Fundamentals) -> float | None:
    """Return the EV/EBITDA ratio from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        EV/EBITDA as a float, or None if not available in the snapshot.
    """
    if snapshot.ev_ebitda is None:
        return None
    return float(snapshot.ev_ebitda)


def dividend_yield(snapshot: Fundamentals) -> float | None:
    """Return the annual dividend yield from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.

    Returns:
        Dividend yield as a decimal fraction (e.g. 0.02 = 2 %), or None.
    """
    if snapshot.dividend_yield is None:
        return None
    return float(snapshot.dividend_yield)


def peg(pe_ratio: float | None, eps_growth_rate: float | None) -> float | None:
    """Compute the PEG ratio: P/E divided by annual EPS growth rate (as a percentage).

    The growth rate must be positive for PEG to be meaningful; negative growth
    or zero growth results in None rather than a nonsensical value.

    Args:
        pe_ratio: Trailing P/E ratio.
        eps_growth_rate: Expected or trailing annual EPS growth rate expressed
            as a percentage (e.g. 15.0 = 15 %). Must be > 0.

    Returns:
        PEG ratio as a float, or None when either input is missing or
        eps_growth_rate <= 0.
    """
    if pe_ratio is None or eps_growth_rate is None:
        return None
    if eps_growth_rate <= 0:
        return None
    return pe_ratio / eps_growth_rate


def compute_valuation_ratios(
    snapshot: Fundamentals,
    eps_growth_rate: float | None = None,
) -> ValuationRatios:
    """Compute all valuation ratios for a ticker from a fundamental snapshot.

    Args:
        snapshot: Latest Fundamentals ORM row for the ticker.
        eps_growth_rate: Optional EPS growth rate (%) used to compute PEG.
            Pass the 1Y or 3Y EPS CAGR from the growth calculator. If None,
            peg will be None.

    Returns:
        A ValuationRatios dataclass with all computed ratios. Any ratio whose
        inputs are missing or invalid will be None.
    """
    _pe = pe(snapshot)
    return ValuationRatios(
        pe=_pe,
        pb=pb(snapshot),
        ps=ps(snapshot),
        ev_ebitda=ev_ebitda(snapshot),
        dividend_yield=dividend_yield(snapshot),
        peg=peg(_pe, eps_growth_rate),
    )
