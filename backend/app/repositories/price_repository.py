"""
Description: Repository for the price_bars table.
             Handles bulk upsert of OHLCV data from provider DTOs and
             range-based retrieval for the prices API endpoint.
             upsert_bars uses session.merge() per row for SQLite/PostgreSQL
             compatibility. Sprint 2 will replace this with a bulk
             INSERT … ON CONFLICT DO NOTHING once tests run against real PG.
             Import aliases used here:
               PriceBarModel  → app.models.price_bar.PriceBar   (ORM row)
               PriceBarDTO    → app.data_providers.models.PriceBar (Pydantic DTO)
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; upsert_bars and get_bars methods.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import PriceBar as PriceBarDTO
from app.models.price_bar import PriceBar as PriceBarModel


class PriceRepository:
    """Data-access object for the price_bars time-series table.

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

    async def upsert_bars(
        self,
        ticker_id: int,
        bars: list[PriceBarDTO],
        interval: str = "1d",
    ) -> int:
        """Persist a batch of provider PriceBars for a ticker.

        Each bar is matched against the unique constraint
        (ticker_id, timestamp, interval). Existing rows are updated;
        new rows are inserted. The operation is idempotent — calling it
        twice with the same data produces no duplicates.

        Note: uses session.merge() per row for SQLite compatibility.
        Sprint 2 will switch to bulk INSERT … ON CONFLICT DO NOTHING
        against real PostgreSQL for performance.

        Args:
            ticker_id: Primary key of the parent Ticker row.
            bars: List of PriceBar DTOs from a MarketDataProvider.
            interval: Bar granularity string (e.g. '1d', '1h'). Applied
                to every bar in this batch.

        Returns:
            Number of rows that were newly inserted (not updated).
        """
        inserted = 0
        for dto in bars:
            ts = dto.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)

            # Check if the row already exists
            result = await self._session.execute(
                select(PriceBarModel).where(
                    PriceBarModel.ticker_id == ticker_id,
                    PriceBarModel.timestamp == ts,
                    PriceBarModel.interval == interval,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                existing.open = Decimal(str(dto.open))
                existing.high = Decimal(str(dto.high))
                existing.low = Decimal(str(dto.low))
                existing.close = Decimal(str(dto.close))
                existing.volume = dto.volume
                existing.adjusted_close = (
                    Decimal(str(dto.adjusted_close)) if dto.adjusted_close is not None else None
                )
            else:
                row = PriceBarModel(
                    ticker_id=ticker_id,
                    timestamp=ts,
                    interval=interval,
                    open=Decimal(str(dto.open)),
                    high=Decimal(str(dto.high)),
                    low=Decimal(str(dto.low)),
                    close=Decimal(str(dto.close)),
                    volume=dto.volume,
                    adjusted_close=(
                        Decimal(str(dto.adjusted_close)) if dto.adjusted_close is not None else None
                    ),
                )
                self._session.add(row)
                inserted += 1

        await self._session.flush()
        return inserted

    async def get_bars(
        self,
        ticker_id: int,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> list[PriceBarModel]:
        """Return ORM PriceBar rows for a ticker in a date range.

        Args:
            ticker_id: Primary key of the parent Ticker row.
            start: First date to include (inclusive, matched against
                the date portion of the UTC timestamp).
            end: Last date to include (inclusive).
            interval: Bar granularity filter. Only rows with this interval
                are returned.

        Returns:
            List of PriceBar ORM instances ordered oldest-first.
        """
        start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)
        # end is inclusive: shift to start of next day to capture all bars on that date
        end_dt = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)

        result = await self._session.execute(
            select(PriceBarModel)
            .where(
                PriceBarModel.ticker_id == ticker_id,
                PriceBarModel.interval == interval,
                PriceBarModel.timestamp >= start_dt,
                PriceBarModel.timestamp < end_dt,
            )
            .order_by(PriceBarModel.timestamp)
        )
        return list(result.scalars().all())
