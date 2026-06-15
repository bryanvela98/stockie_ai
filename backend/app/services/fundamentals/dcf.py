"""
Description: Simplified 2-stage DCF calculator for Stockie AI.
             Operates on the latest annual FinancialStatement for a ticker.

             Model:
               Base FCF  = operating_cash_flow + capital_expenditure
                           (capex is stored negative; addition is correct)
               Stage 1   = project `years` FCF periods at `growth_rate`,
                           discount each at `discount_rate`
               Stage 2   = Gordon Growth terminal value:
                           TV = FCF_n*(1+terminal_growth)/(discount_rate-terminal_growth)
                           discounted back to present
               EV        = sum(discounted FCFs) + PV(terminal value)
               Net debt  = total_debt - cash_and_equivalents  (may be negative)
               Equity    = EV - net_debt
               Per share = equity / shares_diluted

             Important: negative net debt (cash-rich names) is allowed and
             correct — equity value > EV in that case.

             All computation is pure (no I/O inside the math functions). The
             DcfService wraps repo access around the pure core so the router
             stays thin and unit tests can verify the math without a DB.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; DcfResult, pure _compute_dcf(), DcfService.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.models.financial_statement import PERIOD_TYPE_ANNUAL
from app.repositories.financial_statement_repository import FinancialStatementRepository
from app.repositories.ticker_repository import TickerRepository


@dataclass(frozen=True)
class DcfYearProjection:
    """Projected and discounted FCF for a single year."""

    year: int
    projected_fcf: float
    discounted_fcf: float


@dataclass(frozen=True)
class DcfResult:
    """Output of the simplified 2-stage DCF calculation."""

    symbol: str
    intrinsic_value_per_share: float | None
    enterprise_value: float
    equity_value: float
    terminal_value: float
    assumptions: dict[str, float] = field(default_factory=dict)
    yearly_fcf: list[DcfYearProjection] = field(default_factory=list)


def _compute_dcf(
    base_fcf: float,
    shares_diluted: float,
    net_debt: float,
    growth_rate: float,
    discount_rate: float,
    terminal_growth: float,
    years: int,
) -> tuple[float, float, float, float, list[DcfYearProjection]]:
    """Compute the 2-stage DCF and return (EV, equity_value, TV, per_share, yearly).

    Args:
        base_fcf: Most recent annual FCF (operating CF + capex).
        shares_diluted: Diluted share count.
        net_debt: total_debt - cash. May be negative for cash-rich companies.
        growth_rate: Near-term FCF CAGR applied over `years`.
        discount_rate: WACC used to discount future cash flows.
        terminal_growth: Perpetuity growth rate (must be < discount_rate).
        years: Number of explicit projection years.

    Returns:
        Tuple of (enterprise_value, equity_value, terminal_value,
                  intrinsic_value_per_share, yearly_projections).
    """
    yearly: list[DcfYearProjection] = []
    pv_sum = 0.0
    fcf = base_fcf

    for yr in range(1, years + 1):
        fcf = fcf * (1.0 + growth_rate)
        pv = fcf / (1.0 + discount_rate) ** yr
        yearly.append(DcfYearProjection(year=yr, projected_fcf=fcf, discounted_fcf=pv))
        pv_sum += pv

    # Terminal value (Gordon Growth) discounted back
    terminal_fcf = fcf * (1.0 + terminal_growth)
    tv = terminal_fcf / (discount_rate - terminal_growth)
    pv_tv = tv / (1.0 + discount_rate) ** years

    enterprise_value = pv_sum + pv_tv
    equity_value = enterprise_value - net_debt
    per_share = equity_value / shares_diluted if shares_diluted > 0 else None

    return enterprise_value, equity_value, tv, per_share, yearly  # type: ignore[return-value]


class DcfService:
    """Resolves DB data for a ticker and delegates to the pure DCF core.

    Raises TickerNotFoundError when the symbol or its latest annual statement
    is absent from the DB.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an open async database session.

        Args:
            session: Active AsyncSession for repository queries.
        """
        self._session = session
        self._ticker_repo = TickerRepository(session)
        self._stmt_repo = FinancialStatementRepository(session)

    async def compute(
        self,
        symbol: str,
        growth_rate: float,
        discount_rate: float,
        terminal_growth: float,
        years: int,
    ) -> DcfResult:
        """Compute a DCF intrinsic value for the given ticker and assumptions.

        Args:
            symbol: Ticker symbol (case-insensitive).
            growth_rate: Near-term FCF growth rate (0–1).
            discount_rate: WACC discount rate (0–1, must be > terminal_growth).
            terminal_growth: Gordon perpetuity growth rate (must be < discount_rate).
            years: Number of explicit projection periods (1–15).

        Returns:
            DcfResult with per-share intrinsic value and breakdown.

        Raises:
            TickerNotFoundError: When symbol is unknown or has no annual statements.
        """
        symbol = symbol.upper()
        ticker = await self._ticker_repo.get_by_symbol(symbol)
        if ticker is None:
            raise TickerNotFoundError(f"Ticker not found: {symbol}")

        stmts = await self._stmt_repo.get_history(
            ticker.id, period_type=PERIOD_TYPE_ANNUAL, limit=1
        )
        if not stmts:
            raise TickerNotFoundError(f"No annual statements for: {symbol}")

        stmt = stmts[0]

        # Base FCF: capex is negative, so addition is correct (not subtraction).
        ocf = float(stmt.operating_cash_flow or 0)
        capex = float(stmt.capital_expenditure or 0)
        base_fcf = ocf + capex

        shares = float(stmt.shares_diluted or 0)
        debt = float(stmt.total_debt or 0)
        cash = float(stmt.cash_and_equivalents or 0)
        net_debt = debt - cash

        ev, equity, tv, per_share, yearly = _compute_dcf(
            base_fcf=base_fcf,
            shares_diluted=shares,
            net_debt=net_debt,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            terminal_growth=terminal_growth,
            years=years,
        )

        return DcfResult(
            symbol=symbol,
            intrinsic_value_per_share=per_share,
            enterprise_value=ev,
            equity_value=equity,
            terminal_value=tv,
            assumptions={
                "growth_rate": growth_rate,
                "discount_rate": discount_rate,
                "terminal_growth": terminal_growth,
                "years": float(years),
                "base_fcf": base_fcf,
            },
            yearly_fcf=yearly,
        )
