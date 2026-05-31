"""
Description: Pydantic value objects returned by the data provider layer.
             These are pure data containers — no persistence, no business logic.
             They decouple the provider abstractions from SQLAlchemy ORM models;
             the repository layer is responsible for mapping between the two.
             All financial numeric fields are Optional[float] because providers
             (including yfinance) may return NaN or omit fields for some tickers.
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; added TickerInfo, PriceBar, and Fundamentals.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class TickerInfo(BaseModel):
    """Static metadata for a single equity or ETF.

    Populated from a provider's ticker-info endpoint (e.g. yfinance `.info`).
    Fields that the provider does not supply default to None.
    """

    symbol: str = Field(description="Exchange ticker symbol, e.g. 'AAPL'.")
    name: str = Field(description="Human-readable company or fund name.")
    exchange: str = Field(description="Primary exchange, e.g. 'NASDAQ', 'NYSE'.")
    asset_type: str = Field(description="Asset classification, e.g. 'EQUITY', 'ETF', 'MUTUALFUND'.")
    currency: str = Field(default="USD", description="Trading currency (ISO 4217).")
    sector: str | None = Field(default=None, description="GICS sector, if available.")
    industry: str | None = Field(default=None, description="GICS industry, if available.")


class PriceBar(BaseModel):
    """A single OHLCV candlestick for a ticker.

    `adjusted_close` reflects corporate-action adjustments (splits, dividends).
    It may be None if the provider does not supply an adjusted series.
    All price fields are float; precision requirements are handled at the
    storage layer (TimescaleDB NUMERIC columns in future migrations).
    """

    symbol: str = Field(description="Ticker symbol this bar belongs to.")
    timestamp: datetime = Field(description="Bar open time in UTC.")
    open: float = Field(description="Opening price.")
    high: float = Field(description="Intrabar high.")
    low: float = Field(description="Intrabar low.")
    close: float = Field(description="Closing price.")
    volume: int = Field(description="Number of shares traded.")
    adjusted_close: float | None = Field(
        default=None,
        description="Split- and dividend-adjusted closing price, if available.",
    )


class Fundamentals(BaseModel):
    """Latest available fundamental snapshot for a ticker.

    All financial metrics are optional because coverage varies by provider and
    asset type (e.g. ETFs lack earnings-based ratios). Callers must handle None.
    `as_of` is the date the data was published or last refreshed by the provider.
    """

    symbol: str = Field(description="Ticker symbol.")
    as_of: date = Field(description="Date this snapshot was sourced from the provider.")

    # Valuation
    market_cap: int | None = Field(default=None, description="Market capitalisation in USD.")
    pe_ratio: float | None = Field(default=None, description="Price-to-earnings (TTM).")
    pb_ratio: float | None = Field(default=None, description="Price-to-book.")
    ps_ratio: float | None = Field(default=None, description="Price-to-sales (TTM).")
    ev_ebitda: float | None = Field(default=None, description="Enterprise value / EBITDA.")

    # Earnings & revenue
    eps_ttm: float | None = Field(
        default=None, description="Earnings per share, trailing twelve months."
    )
    revenue_ttm: int | None = Field(
        default=None, description="Total revenue, trailing twelve months, in USD."
    )
    net_income_ttm: int | None = Field(
        default=None, description="Net income, trailing twelve months, in USD."
    )

    # Quality metrics
    roe: float | None = Field(default=None, description="Return on equity (decimal, e.g. 0.15).")
    debt_to_equity: float | None = Field(
        default=None, description="Total debt / shareholders' equity."
    )
    dividend_yield: float | None = Field(
        default=None, description="Annual dividend yield (decimal, e.g. 0.02)."
    )

    # Market context
    beta: float | None = Field(default=None, description="Beta relative to the S&P 500 benchmark.")
    week_52_high: float | None = Field(default=None, description="52-week price high.")
    week_52_low: float | None = Field(default=None, description="52-week price low.")
