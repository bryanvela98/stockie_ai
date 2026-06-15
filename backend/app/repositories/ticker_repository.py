"""
Description: Repository for the tickers table.
             All database access for Ticker rows is routed through this class.
             The AsyncSession is injected via the constructor so the caller
             (FastAPI dependency, Celery task) controls the session lifecycle.
             `search` uses func.lower().like() for case-insensitive prefix
             matching that works on both SQLite (tests) and PostgreSQL (prod).
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; get_by_symbol, get_by_id, upsert, search.
    2026-06-09 - Added get_all_active() for Celery ingestion tasks (Sprint 2-B Task 4).
    2026-06-13 - Added get_by_sector() for peer-comparison service.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.models import TickerInfo
from app.models.ticker import Ticker


class TickerRepository:
    """Data-access object for the tickers master table.

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

    async def get_by_symbol(self, symbol: str) -> Ticker | None:
        """Fetch a Ticker by exact symbol (case-insensitive).

        Args:
            symbol: Exchange ticker symbol, e.g. 'AAPL'.

        Returns:
            The matching Ticker row, or None if the symbol is not tracked.
        """
        result = await self._session.execute(
            select(Ticker).where(func.lower(Ticker.symbol) == symbol.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, ticker_id: int) -> Ticker | None:
        """Fetch a Ticker by primary key.

        Args:
            ticker_id: The integer primary key of the row.

        Returns:
            The matching Ticker row, or None if the id does not exist.
        """
        return await self._session.get(Ticker, ticker_id)

    async def upsert(self, info: TickerInfo) -> Ticker:
        """Insert or update a Ticker from a provider TickerInfo value object.

        Matches on symbol (case-insensitive). If the ticker already exists,
        mutable fields (name, exchange, asset_type, currency, sector, industry)
        are updated in place. If it does not exist, a new row is inserted.

        Args:
            info: A TickerInfo DTO returned by a MarketDataProvider.

        Returns:
            The persisted Ticker ORM instance (either new or updated).
        """
        existing = await self.get_by_symbol(info.symbol)
        if existing is not None:
            existing.name = info.name
            existing.exchange = info.exchange
            existing.asset_type = info.asset_type
            existing.currency = info.currency
            existing.sector = info.sector
            existing.industry = info.industry
            await self._session.flush()
            return existing

        ticker = Ticker(
            symbol=info.symbol.upper(),
            name=info.name,
            exchange=info.exchange,
            asset_type=info.asset_type,
            currency=info.currency,
            sector=info.sector,
            industry=info.industry,
        )
        self._session.add(ticker)
        await self._session.flush()  # populates ticker.id
        return ticker

    async def get_all_active(self) -> list[Ticker]:
        """Return all active Ticker rows ordered by symbol.

        Returns:
            List of Ticker rows where is_active is True, ordered by symbol ascending.
        """
        result = await self._session.execute(
            select(Ticker).where(Ticker.is_active.is_(True)).order_by(Ticker.symbol)
        )
        return list(result.scalars().all())

    async def get_by_sector(self, sector: str, exclude_id: int) -> list[Ticker]:
        """Return all active Tickers in the given sector, excluding one ticker.

        Used by the peer-comparison service to fetch candidate peers.

        Args:
            sector: Sector string to filter on (exact match, case-sensitive).
            exclude_id: Primary key of the subject ticker to exclude from results.

        Returns:
            List of Ticker rows in the sector, ordered by symbol.
        """
        result = await self._session.execute(
            select(Ticker)
            .where(
                Ticker.sector == sector,
                Ticker.id != exclude_id,
                Ticker.is_active.is_(True),
            )
            .order_by(Ticker.symbol)
        )
        return list(result.scalars().all())

    async def search(self, query: str, limit: int = 20) -> list[Ticker]:
        """Return Tickers whose symbol or name starts with query (case-insensitive).

        Uses func.lower().like() for portability across SQLite and PostgreSQL.

        Args:
            query: Prefix string to match against symbol and name.
            limit: Maximum number of results to return. Defaults to 20.

        Returns:
            List of matching Ticker rows, ordered by symbol ascending.
        """
        q = query.lower() + "%"
        result = await self._session.execute(
            select(Ticker)
            .where(func.lower(Ticker.symbol).like(q) | func.lower(Ticker.name).like(q))
            .order_by(Ticker.symbol)
            .limit(limit)
        )
        return list(result.scalars().all())
