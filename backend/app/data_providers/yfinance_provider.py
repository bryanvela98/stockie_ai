"""
Description: Concrete data provider backed by the yfinance library.
             Wraps the unofficial Yahoo Finance API to deliver OHLCV price bars,
             fundamental snapshots, and corporate-action history for US equities
             and ETFs.
             All yfinance I/O runs inside asyncio.to_thread to avoid blocking the
             FastAPI event loop, since yfinance is fully synchronous.
             WARNING: yfinance wraps unofficial Yahoo Finance endpoints that may
             change without notice. All field access uses dict.get() so breakage
             degrades gracefully to None rather than raising KeyError.
             See PLANNING_tasks.md §6 — risk: yfinance is unofficial.
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; implemented YFinanceProvider with get_ticker_info,
                 get_price_bars, and get_fundamentals.
    2026-06-09 - Added get_corporate_actions().
    2026-06-12 - Added get_annual_financials().
"""

import asyncio
import math
from datetime import UTC, date
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from app.data_providers.base import FundamentalsProvider, MarketDataProvider
from app.data_providers.exceptions import ProviderError, TickerNotFoundError
from app.data_providers.models import (
    AnnualFinancials,
    CorporateActionDTO,
    Fundamentals,
    PriceBar,
    TickerInfo,
)


def _float_or_none(value: object) -> float | None:
    """Convert a raw provider value to float, returning None for NaN or invalid.

    Args:
        value: A raw value from the yfinance info dict (may be None, NaN, or str).

    Returns:
        Float if the value is a valid finite number; None otherwise.
    """
    if value is None:
        return None
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    """Convert a raw provider value to int, returning None for NaN or invalid.

    Args:
        value: A raw value from the yfinance info dict (often a large integer
               like market cap, but returned as float by yfinance).

    Returns:
        Int if the value is a valid finite number; None otherwise.
    """
    f = _float_or_none(value)
    return None if f is None else int(f)


def _row(df: pd.DataFrame, col: Any, *labels: str) -> object:
    """Extract a cell from a statement DataFrame by trying labels in order.

    yfinance row labels are inconsistent across tickers (e.g. 'Operating Income'
    vs 'EBIT', 'Stockholders Equity' vs 'Common Stock Equity'). This helper
    tries each label in priority order and returns the first match, or None when
    none of the labels are present in the DataFrame index.

    Args:
        df: Annual statement DataFrame (rows = line items, cols = fiscal periods).
        col: Column (fiscal-year-end Timestamp) to read from.
        *labels: Row label candidates in priority order.

    Returns:
        The raw cell value if a matching label is found, otherwise None.
    """
    if col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            return df.at[label, col]
    return None


class YFinanceProvider(MarketDataProvider, FundamentalsProvider):
    """Data provider backed by yfinance (Yahoo Finance unofficial API).

    Implements both MarketDataProvider and FundamentalsProvider because yfinance
    delivers both price data and fundamentals from the same yf.Ticker object.

    All I/O is wrapped with asyncio.to_thread; the class itself is stateless and
    safe to share across coroutines.
    """

    async def get_ticker_info(self, symbol: str) -> TickerInfo:
        """Fetch static metadata for a ticker symbol from Yahoo Finance.

        Args:
            symbol: Exchange ticker symbol, e.g. 'AAPL'.

        Returns:
            A TickerInfo value object populated from the yfinance `.info` dict.

        Raises:
            TickerNotFoundError: If the symbol is not recognised by Yahoo Finance
                (empty info dict or missing quoteType field).
            ProviderError: On network or parse failures.
        """

        def _fetch() -> dict[str, Any]:
            return yf.Ticker(symbol).info  # type: ignore[no-any-return]

        try:
            raw = await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise ProviderError(f"yfinance error fetching info for {symbol!r}: {exc}") from exc

        if not raw or raw.get("quoteType") is None:
            raise TickerNotFoundError(symbol)

        name = raw.get("shortName") or raw.get("longName") or symbol

        return TickerInfo(
            symbol=symbol.upper(),
            name=str(name),
            exchange=str(raw.get("exchange") or "UNKNOWN"),
            asset_type=str(raw.get("quoteType") or "UNKNOWN"),
            currency=str(raw.get("currency") or "USD"),
            sector=str(raw["sector"]) if raw.get("sector") else None,
            industry=str(raw["industry"]) if raw.get("industry") else None,
        )

    async def get_price_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> list[PriceBar]:
        """Fetch OHLCV bars for a symbol via yfinance ticker.history().

        Calls history with auto_adjust=False to obtain both the raw close price
        and the split/dividend-adjusted close in separate columns.

        Args:
            symbol: Exchange ticker symbol.
            start: First date to include (inclusive).
            end: Last date to include (inclusive).
            interval: Bar granularity string accepted by yfinance (e.g. '1d', '1h').

        Returns:
            List of PriceBar objects ordered oldest-first. Returns an empty list
            if Yahoo Finance has no trading data for the requested range.

        Raises:
            ProviderError: On network or parse failures.
        """

        def _fetch() -> Any:
            return yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval,
                auto_adjust=False,
            )

        try:
            df = await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise ProviderError(
                f"yfinance error fetching price bars for {symbol!r}: {exc}"
            ) from exc

        if df.empty:
            return []

        has_adj_close = "Adj Close" in df.columns
        bars: list[PriceBar] = []

        for ts, row in df.iterrows():
            timestamp = ts.to_pydatetime()  # type: ignore[union-attr]
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)

            adj_close = _float_or_none(row.get("Adj Close")) if has_adj_close else None

            bars.append(
                PriceBar(
                    symbol=symbol.upper(),
                    timestamp=timestamp,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    adjusted_close=adj_close,
                )
            )

        return bars

    async def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Fetch the latest fundamental snapshot from the yfinance info dict.

        Note: `debtToEquity` from yfinance is expressed as a percentage
        (e.g. 150 means 150 %) rather than a decimal ratio. Normalisation
        to a standard ratio is the responsibility of the scoring layer.

        Args:
            symbol: Exchange ticker symbol.

        Returns:
            A Fundamentals value object. Fields not supplied by Yahoo Finance
            (or returned as NaN) are mapped to None.

        Raises:
            TickerNotFoundError: If the symbol is not recognised.
            ProviderError: On network or parse failures.
        """

        def _fetch() -> dict[str, Any]:
            return yf.Ticker(symbol).info  # type: ignore[no-any-return]

        try:
            raw = await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise ProviderError(
                f"yfinance error fetching fundamentals for {symbol!r}: {exc}"
            ) from exc

        if not raw or raw.get("quoteType") is None:
            raise TickerNotFoundError(symbol)

        return Fundamentals(
            symbol=symbol.upper(),
            as_of=date.today(),
            market_cap=_int_or_none(raw.get("marketCap")),
            pe_ratio=_float_or_none(raw.get("trailingPE")),
            pb_ratio=_float_or_none(raw.get("priceToBook")),
            ps_ratio=_float_or_none(raw.get("priceToSalesTrailing12Months")),
            ev_ebitda=_float_or_none(raw.get("enterpriseToEbitda")),
            eps_ttm=_float_or_none(raw.get("trailingEps")),
            revenue_ttm=_int_or_none(raw.get("totalRevenue")),
            net_income_ttm=_int_or_none(raw.get("netIncomeToCommon")),
            roe=_float_or_none(raw.get("returnOnEquity")),
            debt_to_equity=_float_or_none(raw.get("debtToEquity")),
            dividend_yield=_float_or_none(raw.get("dividendYield")),
            beta=_float_or_none(raw.get("beta")),
            week_52_high=_float_or_none(raw.get("fiftyTwoWeekHigh")),
            week_52_low=_float_or_none(raw.get("fiftyTwoWeekLow")),
        )

    async def get_corporate_actions(self, symbol: str) -> list[CorporateActionDTO]:
        """Fetch split and dividend history for a symbol from Yahoo Finance.

        yfinance returns splits as a ratio (e.g. 2.0 for a 2-for-1 split) and
        dividends as the cash amount per share. Zero-valued entries are skipped
        as they indicate data artefacts from the yfinance unofficial API.

        Args:
            symbol: Exchange ticker symbol.

        Returns:
            List of CorporateActionDTO objects (splits + dividends combined),
            ordered by ex_date ascending. May be empty for tickers with no
            recorded corporate-action history.

        Raises:
            ProviderError: On network or parse failures.
        """

        def _fetch() -> tuple[Any, Any]:
            t = yf.Ticker(symbol)
            return t.splits, t.dividends

        try:
            splits, dividends = await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise ProviderError(
                f"yfinance error fetching corporate actions for {symbol!r}: {exc}"
            ) from exc

        actions: list[CorporateActionDTO] = []

        for ts, ratio in splits.items():
            if ratio and ratio > 0:
                actions.append(
                    CorporateActionDTO(
                        action_type="split",
                        ex_date=ts.date(),
                        ratio=Decimal(str(ratio)),
                    )
                )

        for ts, amount in dividends.items():
            if amount and amount > 0:
                actions.append(
                    CorporateActionDTO(
                        action_type="dividend",
                        ex_date=ts.date(),
                        ratio=Decimal(str(amount)),
                    )
                )

        actions.sort(key=lambda a: a.ex_date)
        return actions

    async def get_annual_financials(self, symbol: str, years: int = 5) -> list[AnnualFinancials]:
        """Fetch annual financial statement line items from Yahoo Finance.

        Reads income_stmt, balance_sheet, and cashflow DataFrames (annual
        frequency). Each DataFrame column is a fiscal-year-end Timestamp; the
        DataFrames are aligned by that timestamp. Up to `years` columns are
        returned, ordered newest-first.

        yfinance label quirks are handled by _row(), which tries multiple
        alternative row labels in priority order.

        Args:
            symbol: Exchange ticker symbol.
            years: Maximum number of fiscal years to return. Defaults to 5.

        Returns:
            List of AnnualFinancials objects ordered newest-first. May be empty
            for ETFs or any ticker where Yahoo Finance has no statement data.

        Raises:
            ProviderError: On network or parse failures.
        """

        def _fetch() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str | None]:
            t = yf.Ticker(symbol)
            currency: str | None = (t.info or {}).get("currency")
            return t.income_stmt, t.balance_sheet, t.cashflow, currency

        try:
            income, balance, cashflow, currency = await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise ProviderError(
                f"yfinance error fetching annual financials for {symbol!r}: {exc}"
            ) from exc

        if income is None or income.empty:
            return []

        # Columns are fiscal-year-end Timestamps, newest first
        cols = income.columns[:years]

        results: list[AnnualFinancials] = []
        for col in cols:
            results.append(
                AnnualFinancials(
                    fiscal_year=col.year,
                    currency=currency,
                    total_revenue=_int_or_none(_row(income, col, "Total Revenue")),
                    gross_profit=_int_or_none(_row(income, col, "Gross Profit")),
                    operating_income=_int_or_none(_row(income, col, "Operating Income", "EBIT")),
                    net_income=_int_or_none(_row(income, col, "Net Income")),
                    interest_expense=_int_or_none(_row(income, col, "Interest Expense")),
                    eps_diluted=_float_or_none(_row(income, col, "Diluted EPS")),
                    total_assets=_int_or_none(_row(balance, col, "Total Assets")),
                    total_equity=_int_or_none(
                        _row(
                            balance,
                            col,
                            "Stockholders Equity",
                            "Common Stock Equity",
                            "Total Equity Gross Minority Interest",
                        )
                    ),
                    total_debt=_int_or_none(_row(balance, col, "Total Debt")),
                    cash_and_equivalents=_int_or_none(
                        _row(
                            balance,
                            col,
                            "Cash And Cash Equivalents",
                            "Cash Cash Equivalents And Short Term Investments",
                        )
                    ),
                    operating_cash_flow=_int_or_none(_row(cashflow, col, "Operating Cash Flow")),
                    capital_expenditure=_int_or_none(_row(cashflow, col, "Capital Expenditure")),
                    shares_diluted=_int_or_none(_row(income, col, "Diluted Average Shares")),
                )
            )

        return results
