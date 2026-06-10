"""
Description: Repository for the corporate_actions table.
             Handles idempotent upsert and retrieval of stock splits and
             cash dividends per ticker.
             upsert() is safe to call multiple times for the same event —
             the unique constraint on (ticker_id, action_type, ex_date) means
             a second call with identical data updates the ratio in-place.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; upsert and get_by_ticker methods (Sprint 2-B Task 2).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corporate_action import (
    ACTION_TYPE_DIVIDEND,
    ACTION_TYPE_SPLIT,
    CorporateAction,
)

__all__ = [
    "ACTION_TYPE_DIVIDEND",
    "ACTION_TYPE_SPLIT",
    "CorporateActionCreate",
    "CorporateActionRepository",
]


@dataclass(frozen=True)
class CorporateActionCreate:
    """Value object carrying the data needed to insert or update a corporate action."""

    ticker_id: int
    action_type: str  # "split" | "dividend"
    ex_date: date
    ratio: Decimal


class CorporateActionRepository:
    """Data-access object for the corporate_actions table.

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

    async def upsert(self, action: CorporateActionCreate) -> CorporateAction:
        """Insert or update a corporate-action event.

        Matches on the unique key (ticker_id, action_type, ex_date). If the
        row already exists, the ratio is updated in-place. The operation is
        idempotent — calling it twice with the same key produces one row.

        Args:
            action: Value object describing the corporate action to persist.

        Returns:
            The persisted CorporateAction ORM instance (new or updated).
        """
        result = await self._session.execute(
            select(CorporateAction).where(
                CorporateAction.ticker_id == action.ticker_id,
                CorporateAction.action_type == action.action_type,
                CorporateAction.ex_date == action.ex_date,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.ratio = action.ratio
            await self._session.flush()
            return existing

        row = CorporateAction(
            ticker_id=action.ticker_id,
            action_type=action.action_type,
            ex_date=action.ex_date,
            ratio=action.ratio,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_ticker(
        self,
        ticker_id: int,
        since: date | None = None,
    ) -> list[CorporateAction]:
        """Return corporate actions for a ticker, optionally filtered by date.

        Args:
            ticker_id: Primary key of the parent Ticker row.
            since: If provided, only actions with ex_date >= since are returned.

        Returns:
            List of CorporateAction ORM instances ordered by ex_date ascending.
        """
        stmt = (
            select(CorporateAction)
            .where(CorporateAction.ticker_id == ticker_id)
            .order_by(CorporateAction.ex_date)
        )
        if since is not None:
            stmt = stmt.where(CorporateAction.ex_date >= since)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
