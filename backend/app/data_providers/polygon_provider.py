"""
Description: Stub provider for the Polygon.io API (not yet implemented).
             This class satisfies both MarketDataProvider and FundamentalsProvider
             contracts so the abstraction can be verified without a real Polygon
             integration. Every method raises NotImplementedError to signal that
             the implementation is intentionally deferred.
             Polygon.io is the planned paid fallback if yfinance breaks.
             See PLANNING_tasks.md §6 — risk: yfinance is unofficial.
             Full implementation is scheduled for Sprint 2+ when yfinance proves
             insufficient or unreliable.
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; stub with NotImplementedError on all methods.
"""

from datetime import date

from app.data_providers.base import FundamentalsProvider, MarketDataProvider
from app.data_providers.models import Fundamentals, PriceBar, TickerInfo


class PolygonProvider(MarketDataProvider, FundamentalsProvider):
    """Polygon.io data provider — stub only, not yet implemented.

    Proves that the MarketDataProvider / FundamentalsProvider abstractions can
    accommodate a second concrete provider without modifying any caller code.
    Replace each NotImplementedError with a real Polygon REST client call when
    the Polygon integration is scheduled.
    """

    async def get_ticker_info(self, symbol: str) -> TickerInfo:
        """Not implemented — Polygon integration is deferred.

        Args:
            symbol: Exchange ticker symbol.

        Raises:
            NotImplementedError: Always. Implement in a future sprint.
        """
        raise NotImplementedError("PolygonProvider.get_ticker_info is not yet implemented")

    async def get_price_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> list[PriceBar]:
        """Not implemented — Polygon integration is deferred.

        Args:
            symbol: Exchange ticker symbol.
            start: First date to include.
            end: Last date to include.
            interval: Bar granularity.

        Raises:
            NotImplementedError: Always. Implement in a future sprint.
        """
        raise NotImplementedError("PolygonProvider.get_price_bars is not yet implemented")

    async def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Not implemented — Polygon integration is deferred.

        Args:
            symbol: Exchange ticker symbol.

        Raises:
            NotImplementedError: Always. Implement in a future sprint.
        """
        raise NotImplementedError("PolygonProvider.get_fundamentals is not yet implemented")
