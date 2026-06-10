"""
Description: Abstract base classes (ABCs) that define the data-provider contracts.
             All concrete providers (YFinance, Polygon, etc.) must implement these
             interfaces, which enforces Dependency Inversion: higher-level modules
             (services, repositories) depend on these abstractions, never on a
             specific provider library.
             MarketDataProvider handles OHLCV price data and corporate actions.
             FundamentalsProvider handles financial statement data and key ratios.
             A single class may implement both (e.g. YFinanceProvider does).
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; added MarketDataProvider and FundamentalsProvider ABCs.
    2026-06-09 - Added get_corporate_actions() to MarketDataProvider (Sprint 2-B Task 6).
"""

from abc import ABC, abstractmethod
from datetime import date

from app.data_providers.exceptions import (
    TickerNotFoundError,  # noqa: F401 (re-exported for callers)
)
from app.data_providers.models import CorporateActionDTO, Fundamentals, PriceBar, TickerInfo


class MarketDataProvider(ABC):
    """Contract for fetching ticker metadata and OHLCV price bars.

    Concrete implementations wrap specific data sources (yfinance, Polygon, etc.).
    All methods are async to avoid blocking the FastAPI event loop.
    Implementations must raise TickerNotFoundError when a symbol cannot be resolved.
    """

    @abstractmethod
    async def get_ticker_info(self, symbol: str) -> TickerInfo:
        """Fetch static metadata for a single ticker symbol.

        Args:
            symbol: Exchange ticker symbol, e.g. 'AAPL'.

        Returns:
            A TickerInfo value object with name, exchange, asset type, etc.

        Raises:
            TickerNotFoundError: If the symbol does not exist in this provider.
            ProviderError: On transient failures (network, rate limit, parse error).
        """

    @abstractmethod
    async def get_price_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> list[PriceBar]:
        """Fetch OHLCV candlestick bars for a symbol within a date range.

        Args:
            symbol: Exchange ticker symbol.
            start: First date to include (inclusive).
            end: Last date to include (inclusive).
            interval: Bar granularity. Supported values depend on the provider;
                '1d' (daily) is universally supported. Common options: '1h', '1wk'.

        Returns:
            List of PriceBar objects ordered oldest-first. May be empty if no
            trading data exists for the requested range (e.g. weekends).

        Raises:
            TickerNotFoundError: If the symbol does not exist in this provider.
            ProviderError: On transient failures.
        """

    @abstractmethod
    async def get_corporate_actions(self, symbol: str) -> list[CorporateActionDTO]:
        """Fetch the full history of splits and dividends for a symbol.

        Args:
            symbol: Exchange ticker symbol.

        Returns:
            List of CorporateActionDTO objects (splits and dividends combined),
            ordered by ex_date ascending. May be empty if the provider has no
            corporate-action history for this symbol.

        Raises:
            TickerNotFoundError: If the symbol does not exist in this provider.
            ProviderError: On transient failures.
        """


class FundamentalsProvider(ABC):
    """Contract for fetching financial statement data and key ratios.

    Separate from MarketDataProvider per Interface Segregation: callers that
    only need price data (e.g. the technical analysis module) do not depend on
    this interface.
    """

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Fetch the latest available fundamental snapshot for a symbol.

        Args:
            symbol: Exchange ticker symbol.

        Returns:
            A Fundamentals value object. Financial fields that the provider
            does not supply will be None.

        Raises:
            TickerNotFoundError: If the symbol does not exist in this provider.
            ProviderError: On transient failures.
        """
