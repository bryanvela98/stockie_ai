"""
Description: Public API for the data_providers package.
             Re-exports the interfaces, value objects, and exceptions that the
             rest of the application depends on. Concrete providers (YFinance,
             Polygon) are intentionally not exported here — callers should
             depend on the abstractions, not the implementations.
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; barrel export for interfaces, models, exceptions.
    2026-06-12 - Exported AnnualFinancials DTO.
"""

from app.data_providers.base import FundamentalsProvider, MarketDataProvider
from app.data_providers.exceptions import ProviderError, TickerNotFoundError
from app.data_providers.models import AnnualFinancials, Fundamentals, PriceBar, TickerInfo

__all__ = [
    "AnnualFinancials",
    "FundamentalsProvider",
    "Fundamentals",
    "MarketDataProvider",
    "PriceBar",
    "ProviderError",
    "TickerInfo",
    "TickerNotFoundError",
]
