"""
Description: Repository for the fundamentals table.
             Handles idempotent upsert of quarterly fundamental snapshots and
             retrieval of the most recent snapshot per ticker.
             One row per (ticker_id, as_of) date — enforced by unique constraint.
             Sprint 3 will extend this with scoring-specific queries; this file
             intentionally stays narrow (upsert + get_latest only).
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; upsert and get_latest methods (Sprint 2-B Task 3).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fundamentals import Fundamentals

__all__ = ["FundamentalsCreate", "FundamentalsRepository"]


@dataclass(frozen=True)
class FundamentalsCreate:
    """Value object carrying the data needed to insert or update a fundamentals snapshot."""

    ticker_id: int
    as_of: date
    market_cap: int | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    ps_ratio: Decimal | None = None
    ev_ebitda: Decimal | None = None
    eps_ttm: Decimal | None = None
    revenue_ttm: int | None = None
    net_income_ttm: int | None = None
    roe: Decimal | None = None
    debt_to_equity: Decimal | None = None
    dividend_yield: Decimal | None = None
    beta: Decimal | None = None
    week_52_high: Decimal | None = None
    week_52_low: Decimal | None = None


class FundamentalsRepository:
    """Data-access object for the fundamentals table.

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

    async def upsert(self, snapshot: FundamentalsCreate) -> Fundamentals:
        """Insert or update a fundamental snapshot.

        Matches on the unique key (ticker_id, as_of). If the row already
        exists all metric fields are updated in-place. The operation is
        idempotent — calling it twice with the same key produces one row.

        Args:
            snapshot: Value object describing the snapshot to persist.

        Returns:
            The persisted Fundamentals ORM instance (new or updated).
        """
        result = await self._session.execute(
            select(Fundamentals).where(
                Fundamentals.ticker_id == snapshot.ticker_id,
                Fundamentals.as_of == snapshot.as_of,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.market_cap = snapshot.market_cap
            existing.pe_ratio = snapshot.pe_ratio
            existing.pb_ratio = snapshot.pb_ratio
            existing.ps_ratio = snapshot.ps_ratio
            existing.ev_ebitda = snapshot.ev_ebitda
            existing.eps_ttm = snapshot.eps_ttm
            existing.revenue_ttm = snapshot.revenue_ttm
            existing.net_income_ttm = snapshot.net_income_ttm
            existing.roe = snapshot.roe
            existing.debt_to_equity = snapshot.debt_to_equity
            existing.dividend_yield = snapshot.dividend_yield
            existing.beta = snapshot.beta
            existing.week_52_high = snapshot.week_52_high
            existing.week_52_low = snapshot.week_52_low
            await self._session.flush()
            return existing

        row = Fundamentals(
            ticker_id=snapshot.ticker_id,
            as_of=snapshot.as_of,
            market_cap=snapshot.market_cap,
            pe_ratio=snapshot.pe_ratio,
            pb_ratio=snapshot.pb_ratio,
            ps_ratio=snapshot.ps_ratio,
            ev_ebitda=snapshot.ev_ebitda,
            eps_ttm=snapshot.eps_ttm,
            revenue_ttm=snapshot.revenue_ttm,
            net_income_ttm=snapshot.net_income_ttm,
            roe=snapshot.roe,
            debt_to_equity=snapshot.debt_to_equity,
            dividend_yield=snapshot.dividend_yield,
            beta=snapshot.beta,
            week_52_high=snapshot.week_52_high,
            week_52_low=snapshot.week_52_low,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_latest(self, ticker_id: int) -> Fundamentals | None:
        """Return the most recent fundamental snapshot for a ticker.

        Args:
            ticker_id: Primary key of the parent Ticker row.

        Returns:
            The Fundamentals row with the highest as_of date, or None if no
            snapshots exist for this ticker.
        """
        result = await self._session.execute(
            select(Fundamentals)
            .where(Fundamentals.ticker_id == ticker_id)
            .order_by(Fundamentals.as_of.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
