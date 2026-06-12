"""
Description: Tickers API router.
             Exposes endpoints for ticker resolution and price data:
               GET /tickers/search?q=           — prefix search on symbol and name
               GET /tickers/{symbol}            — single-ticker lookup by symbol
               GET /tickers/{symbol}/prices     — paginated OHLCV bars with optional
                                                  timeframe, date-range, and cursor
             All endpoints delegate to the appropriate repository and return Pydantic
             response models so FastAPI generates accurate OpenAPI types for the
             frontend schema.d.ts auto-generation step.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; search and detail endpoints.
    2026-06-09 - Added data_as_of field to TickerSearchResult and GET /{symbol} handler.
    2026-06-11 - Added GET /{symbol}/prices endpoint with cursor-based pagination.
"""

import base64
from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.ticker import Ticker
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository

router = APIRouter(tags=["tickers"])
_log = structlog.get_logger(__name__)


# ── Response models ───────────────────────────────────────────────────────────


class TickerSearchResult(BaseModel):
    """Single ticker entry returned by search and detail endpoints."""

    symbol: str
    name: str
    exchange: str
    asset_type: str
    currency: str
    sector: str | None = None
    industry: str | None = None
    # Freshness indicator: MAX(price_bars.timestamp) for this ticker, or null if no data yet.
    data_as_of: datetime | None = None


class TickerSearchResponse(BaseModel):
    """Paginated response wrapper for the search endpoint."""

    results: list[TickerSearchResult]
    total: int


class PriceBarItem(BaseModel):
    """A single OHLCV candlestick bar.

    Field names are compact for wire efficiency. `low` is spelled out to avoid
    the ambiguous single-letter name `l`.
    """

    t: datetime
    o: float
    h: float
    low: float
    c: float
    v: int
    adj_c: float | None = None


class PriceBarPageResponse(BaseModel):
    """Paginated OHLCV response for a single ticker and timeframe."""

    symbol: str
    timeframe: str
    data_as_of: datetime | None = None
    bars: list[PriceBarItem]
    next_cursor: str | None = None


_MAX_LIMIT = 2000
_DEFAULT_LIMIT = 500
_VALID_TIMEFRAMES = {"1d", "1w", "1mo"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _encode_cursor(ts: datetime) -> str:
    """Encode a UTC datetime as a URL-safe base64 cursor string.

    Args:
        ts: Timestamp of the last returned bar.

    Returns:
        A base64url-encoded ISO 8601 string safe for use as a query parameter.
    """
    return base64.urlsafe_b64encode(ts.isoformat().encode()).decode()


def _decode_cursor(cursor: str) -> datetime | None:
    """Decode a cursor string back to a UTC datetime.

    Args:
        cursor: Value previously returned in `next_cursor`.

    Returns:
        The decoded datetime, or None if the cursor is malformed.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    except Exception:
        return None


def _to_result(ticker: Ticker) -> TickerSearchResult:
    """Map a Ticker ORM row to the API response model.

    Args:
        ticker: A Ticker ORM instance loaded from the database.

    Returns:
        A TickerSearchResult populated from the ORM fields.
    """
    return TickerSearchResult(
        symbol=ticker.symbol,
        name=ticker.name,
        exchange=ticker.exchange,
        asset_type=ticker.asset_type,
        currency=ticker.currency,
        sector=ticker.sector,
        industry=ticker.industry,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/search",
    response_model=TickerSearchResponse,
    summary="Search tickers by symbol or name prefix",
)
async def search_tickers(
    q: str = Query(..., min_length=1, description="Symbol or name prefix, e.g. 'APP'"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db),
) -> TickerSearchResponse:
    """Return tickers whose symbol or name starts with the query string.

    The search is case-insensitive and matches on both the exchange symbol
    and the full company/fund name.

    Args:
        q: Prefix string to search for.
        limit: Maximum number of results. Capped at 50.
        db: Injected async database session.

    Returns:
        TickerSearchResponse with a list of matching tickers and a total count.
    """
    _log.debug("ticker search", q=q, limit=limit)
    repo = TickerRepository(db)
    tickers = await repo.search(q, limit=limit)
    results = [_to_result(t) for t in tickers]
    return TickerSearchResponse(results=results, total=len(results))


@router.get(
    "/{symbol}",
    response_model=TickerSearchResult,
    summary="Get a single ticker by symbol",
)
async def get_ticker(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> TickerSearchResult:
    """Fetch metadata for a single ticker by its exchange symbol.

    The lookup is case-insensitive.

    Args:
        symbol: Exchange ticker symbol, e.g. 'AAPL'.
        db: Injected async database session.

    Returns:
        TickerSearchResult for the matched ticker.

    Raises:
        HTTPException 404: If no ticker with the given symbol exists in the database.
    """
    _log.debug("ticker detail", symbol=symbol)
    ticker_repo = TickerRepository(db)
    ticker = await ticker_repo.get_by_symbol(symbol)
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker not found: '{symbol.upper()}'")
    data_as_of = await PriceRepository(db).get_latest_timestamp(ticker.id)
    result = _to_result(ticker)
    result.data_as_of = data_as_of
    return result


@router.get(
    "/{symbol}/prices",
    response_model=PriceBarPageResponse,
    summary="Get paginated OHLCV price bars for a ticker",
)
async def get_ticker_prices(
    symbol: str,
    timeframe: str = Query(default="1d", description="Bar granularity: '1d', '1w', or '1mo'"),
    from_date: date = Query(
        alias="from", description="Start date (inclusive), ISO format YYYY-MM-DD"
    ),
    to_date: date = Query(alias="to", description="End date (inclusive), ISO format YYYY-MM-DD"),
    limit: int = Query(
        default=_DEFAULT_LIMIT,
        ge=1,
        le=_MAX_LIMIT,
        description=f"Maximum bars per page. Max {_MAX_LIMIT}.",
    ),
    cursor: str | None = Query(default=None, description="Opaque cursor for the next page"),
    db: AsyncSession = Depends(get_db),
) -> PriceBarPageResponse:
    """Return paginated OHLCV candlestick bars for a ticker.

    Bars are ordered oldest-first. When a `next_cursor` is present in the
    response, pass it as `cursor` in the next request to retrieve the
    following page.

    Args:
        symbol: Exchange ticker symbol, e.g. 'AAPL'.
        timeframe: Bar granularity stored in price_bars.interval. Defaults to '1d'.
        from_date: Inclusive start date for the query window.
        to_date: Inclusive end date for the query window.
        limit: Maximum number of bars to return per page.
        cursor: Opaque pagination cursor returned by a previous response.
        db: Injected async database session.

    Returns:
        PriceBarPageResponse containing bars and an optional next_cursor.

    Raises:
        HTTPException 400: If from_date > to_date or timeframe is invalid.
        HTTPException 404: If no ticker with the given symbol exists.
    """
    _log.debug(
        "ticker prices", symbol=symbol, timeframe=timeframe, from_date=from_date, to_date=to_date
    )

    if timeframe not in _VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Must be one of: {', '.join(sorted(_VALID_TIMEFRAMES))}",
        )
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' must not be later than 'to'")

    ticker_repo = TickerRepository(db)
    ticker = await ticker_repo.get_by_symbol(symbol)
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker not found: '{symbol.upper()}'")

    price_repo = PriceRepository(db)

    after_ts: datetime | None = None
    if cursor is not None:
        after_ts = _decode_cursor(cursor)
        if after_ts is None:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    # Fetch one extra bar to detect whether a next page exists.
    rows = await price_repo.get_bars(
        ticker.id,
        from_date,
        to_date,
        interval=timeframe,
        limit=limit + 1,
        after_ts=after_ts,
    )

    has_next = len(rows) > limit
    page = rows[:limit]

    next_cursor = _encode_cursor(page[-1].timestamp) if has_next and page else None

    data_as_of = await price_repo.get_latest_timestamp(ticker.id)

    bars = [
        PriceBarItem(
            t=row.timestamp,
            o=float(row.open),
            h=float(row.high),
            low=float(row.low),
            c=float(row.close),
            v=row.volume,
            adj_c=float(row.adjusted_close) if row.adjusted_close is not None else None,
        )
        for row in page
    ]

    return PriceBarPageResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        data_as_of=data_as_of,
        bars=bars,
        next_cursor=next_cursor,
    )
