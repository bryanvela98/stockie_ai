"""
Description: Unit tests for PolygonProvider stub.
             Verifies that the stub satisfies the ABC contracts (instantiation
             succeeds, isinstance checks pass) and that every method raises
             NotImplementedError when called, as expected for an unimplemented
             provider.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; 6 test cases for instantiation and method stubs.
"""

from datetime import date

import pytest

from app.data_providers import FundamentalsProvider, MarketDataProvider
from app.data_providers.polygon_provider import PolygonProvider


def test_polygon_provider_instantiates() -> None:
    """PolygonProvider() must not raise — the ABC contract is satisfied."""
    provider = PolygonProvider()
    assert provider is not None


def test_polygon_provider_is_market_data_provider() -> None:
    """PolygonProvider must satisfy the MarketDataProvider interface."""
    assert isinstance(PolygonProvider(), MarketDataProvider)


def test_polygon_provider_is_fundamentals_provider() -> None:
    """PolygonProvider must satisfy the FundamentalsProvider interface."""
    assert isinstance(PolygonProvider(), FundamentalsProvider)


@pytest.mark.asyncio
async def test_get_ticker_info_raises_not_implemented() -> None:
    """get_ticker_info must raise NotImplementedError until the sprint is done."""
    with pytest.raises(NotImplementedError):
        await PolygonProvider().get_ticker_info("AAPL")


@pytest.mark.asyncio
async def test_get_price_bars_raises_not_implemented() -> None:
    """get_price_bars must raise NotImplementedError until the sprint is done."""
    with pytest.raises(NotImplementedError):
        await PolygonProvider().get_price_bars(
            "AAPL",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )


@pytest.mark.asyncio
async def test_get_fundamentals_raises_not_implemented() -> None:
    """get_fundamentals must raise NotImplementedError until the sprint is done."""
    with pytest.raises(NotImplementedError):
        await PolygonProvider().get_fundamentals("AAPL")
