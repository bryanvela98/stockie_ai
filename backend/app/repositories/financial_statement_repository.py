"""
Description: Repository for the financial_statements table.
             Handles idempotent upsert of annual (and future quarterly) financial
             statement line items and retrieval of historical rows per ticker.
             One row per (ticker_id, fiscal_year, period_type) — enforced by the
             unique constraint on the table.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; upsert and get_history methods.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_statement import PERIOD_TYPE_ANNUAL, FinancialStatement

__all__ = ["FinancialStatementCreate", "FinancialStatementRepository"]


@dataclass(frozen=True)
class FinancialStatementCreate:
    """Value object carrying the data needed to insert or update a financial statement row."""

    ticker_id: int
    fiscal_year: int
    period_type: str = PERIOD_TYPE_ANNUAL
    currency: str | None = None

    # Income statement
    total_revenue: int | None = None
    gross_profit: int | None = None
    operating_income: int | None = None
    net_income: int | None = None
    interest_expense: int | None = None
    eps_diluted: Decimal | None = None

    # Balance sheet
    total_assets: int | None = None
    total_equity: int | None = None
    total_debt: int | None = None
    cash_and_equivalents: int | None = None

    # Cash flow
    operating_cash_flow: int | None = None
    capital_expenditure: int | None = None

    # Share count
    shares_diluted: int | None = None


class FinancialStatementRepository:
    """Data-access object for the financial_statements table.

    All methods operate on the AsyncSession provided at construction time.
    No session lifecycle management happens here — the caller is responsible
    for committing or rolling back.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an open async session.

        Args:
            session: An AsyncSession bound to an active database connection.
        """
        self._session = session

    async def upsert(self, stmt: FinancialStatementCreate) -> FinancialStatement:
        """Insert or update a financial statement row.

        Matches on the unique key (ticker_id, fiscal_year, period_type). If the
        row already exists all financial fields are updated in-place. The
        operation is idempotent — calling it twice with the same key produces
        one row.

        Args:
            stmt: Value object describing the statement to persist.

        Returns:
            The persisted FinancialStatement ORM instance (new or updated).
        """
        result = await self._session.execute(
            select(FinancialStatement).where(
                FinancialStatement.ticker_id == stmt.ticker_id,
                FinancialStatement.fiscal_year == stmt.fiscal_year,
                FinancialStatement.period_type == stmt.period_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.currency = stmt.currency
            existing.total_revenue = stmt.total_revenue
            existing.gross_profit = stmt.gross_profit
            existing.operating_income = stmt.operating_income
            existing.net_income = stmt.net_income
            existing.interest_expense = stmt.interest_expense
            existing.eps_diluted = stmt.eps_diluted
            existing.total_assets = stmt.total_assets
            existing.total_equity = stmt.total_equity
            existing.total_debt = stmt.total_debt
            existing.cash_and_equivalents = stmt.cash_and_equivalents
            existing.operating_cash_flow = stmt.operating_cash_flow
            existing.capital_expenditure = stmt.capital_expenditure
            existing.shares_diluted = stmt.shares_diluted
            await self._session.flush()
            return existing

        row = FinancialStatement(
            ticker_id=stmt.ticker_id,
            fiscal_year=stmt.fiscal_year,
            period_type=stmt.period_type,
            currency=stmt.currency,
            total_revenue=stmt.total_revenue,
            gross_profit=stmt.gross_profit,
            operating_income=stmt.operating_income,
            net_income=stmt.net_income,
            interest_expense=stmt.interest_expense,
            eps_diluted=stmt.eps_diluted,
            total_assets=stmt.total_assets,
            total_equity=stmt.total_equity,
            total_debt=stmt.total_debt,
            cash_and_equivalents=stmt.cash_and_equivalents,
            operating_cash_flow=stmt.operating_cash_flow,
            capital_expenditure=stmt.capital_expenditure,
            shares_diluted=stmt.shares_diluted,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_history(
        self,
        ticker_id: int,
        period_type: str = PERIOD_TYPE_ANNUAL,
        limit: int = 6,
    ) -> list[FinancialStatement]:
        """Return the most recent financial statement rows for a ticker.

        Args:
            ticker_id: Primary key of the parent Ticker row.
            period_type: Statement frequency to filter on. Defaults to 'annual'.
            limit: Maximum number of rows to return. Defaults to 6.

        Returns:
            List of FinancialStatement rows ordered by fiscal_year descending
            (most recent first), capped at `limit`.
        """
        result = await self._session.execute(
            select(FinancialStatement)
            .where(
                FinancialStatement.ticker_id == ticker_id,
                FinancialStatement.period_type == period_type,
            )
            .order_by(FinancialStatement.fiscal_year.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
