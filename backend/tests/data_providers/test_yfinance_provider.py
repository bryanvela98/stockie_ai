"""
Description: Unit tests for YFinanceProvider.
             All yfinance I/O is mocked — no real network calls are made.
             Tests cover the three public methods, happy paths, TickerNotFoundError
             paths, and NaN-to-None conversion for missing fundamentals fields.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; 7 test cases covering get_ticker_info,
                 get_price_bars, and get_fundamentals.
"""

from datetime import UTC, date, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from app.data_providers.exceptions import TickerNotFoundError
from app.data_providers.models import Fundamentals, PriceBar, TickerInfo
from app.data_providers.yfinance_provider import YFinanceProvider

# ── helpers ──────────────────────────────────────────────────────────────────

_AAPL_INFO: dict[str, object] = {
    "quoteType": "EQUITY",
    "shortName": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "marketCap": 3_000_000_000_000,
    "trailingPE": 29.5,
    "priceToBook": 46.2,
    "priceToSalesTrailing12Months": 8.1,
    "enterpriseToEbitda": 23.4,
    "trailingEps": 6.43,
    "totalRevenue": 400_000_000_000,
    "netIncomeToCommon": 95_000_000_000,
    "returnOnEquity": 1.47,
    "debtToEquity": 150.0,
    "dividendYield": 0.005,
    "beta": 1.24,
    "fiftyTwoWeekHigh": 199.62,
    "fiftyTwoWeekLow": 124.17,
}


def _make_price_df() -> pd.DataFrame:
    """Return a minimal single-row OHLCV DataFrame matching yfinance output."""
    return pd.DataFrame(
        {
            "Open": [150.0],
            "High": [152.0],
            "Low": [149.5],
            "Close": [151.0],
            "Adj Close": [150.8],
            "Volume": [50_000_000],
            "Dividends": [0.0],
            "Stock Splits": [0.0],
        },
        index=pd.DatetimeIndex([datetime(2024, 1, 2, tzinfo=UTC)]),
    )


# ── get_ticker_info ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ticker_info_returns_ticker_info() -> None:
    """Happy path: valid info dict maps to a fully populated TickerInfo."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = _AAPL_INFO
        result = await YFinanceProvider().get_ticker_info("AAPL")

    assert isinstance(result, TickerInfo)
    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.exchange == "NASDAQ"
    assert result.asset_type == "EQUITY"
    assert result.currency == "USD"
    assert result.sector == "Technology"
    assert result.industry == "Consumer Electronics"


@pytest.mark.asyncio
async def test_get_ticker_info_raises_on_empty_info() -> None:
    """An empty info dict means the symbol is not in Yahoo Finance's universe."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {}
        with pytest.raises(TickerNotFoundError) as exc_info:
            await YFinanceProvider().get_ticker_info("FAKE")

    assert exc_info.value.symbol == "FAKE"


@pytest.mark.asyncio
async def test_get_ticker_info_raises_when_quote_type_missing() -> None:
    """A dict without quoteType is treated as a not-found response."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"shortName": "Some Fund"}
        with pytest.raises(TickerNotFoundError):
            await YFinanceProvider().get_ticker_info("XYZ")


# ── get_price_bars ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_price_bars_returns_list_of_price_bars() -> None:
    """Happy path: one-row DataFrame maps to a single PriceBar."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df()
        result = await YFinanceProvider().get_price_bars(
            "AAPL",
            start=date(2024, 1, 2),
            end=date(2024, 1, 2),
        )

    assert len(result) == 1
    bar = result[0]
    assert isinstance(bar, PriceBar)
    assert bar.symbol == "AAPL"
    assert bar.open == pytest.approx(150.0)
    assert bar.high == pytest.approx(152.0)
    assert bar.low == pytest.approx(149.5)
    assert bar.close == pytest.approx(151.0)
    assert bar.adjusted_close == pytest.approx(150.8)
    assert bar.volume == 50_000_000


@pytest.mark.asyncio
async def test_get_price_bars_returns_empty_list_for_no_data() -> None:
    """When yfinance returns an empty DataFrame (e.g. weekend range) → []."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        result = await YFinanceProvider().get_price_bars(
            "AAPL",
            start=date(2024, 1, 6),  # Saturday
            end=date(2024, 1, 6),
        )

    assert result == []


# ── get_fundamentals ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fundamentals_returns_fundamentals() -> None:
    """Happy path: valid info dict maps to a populated Fundamentals object."""
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = _AAPL_INFO
        result = await YFinanceProvider().get_fundamentals("AAPL")

    assert isinstance(result, Fundamentals)
    assert result.symbol == "AAPL"
    assert result.as_of == date.today()
    assert result.market_cap == 3_000_000_000_000
    assert result.pe_ratio == pytest.approx(29.5)
    assert result.beta == pytest.approx(1.24)
    assert result.week_52_high == pytest.approx(199.62)


@pytest.mark.asyncio
async def test_get_fundamentals_nan_fields_become_none() -> None:
    """Fields returned as float('nan') by yfinance must map to None."""
    nan_info: dict[str, object] = {
        "quoteType": "EQUITY",
        "shortName": "Test Co",
        "exchange": "NYSE",
        "trailingPE": float("nan"),
        "priceToBook": float("nan"),
        "beta": float("nan"),
    }
    with patch("app.data_providers.yfinance_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = nan_info
        result = await YFinanceProvider().get_fundamentals("TEST")

    assert result.pe_ratio is None
    assert result.pb_ratio is None
    assert result.beta is None
    # Fields entirely absent from the dict also map to None
    assert result.market_cap is None
    assert result.revenue_ttm is None
