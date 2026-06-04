"""
Description: Tickers API router.
             Exposes two endpoints for the ticker resolution feature:
               GET /tickers/search?q= — prefix search on symbol and name
               GET /tickers/{symbol}  — single-ticker lookup by symbol
             Both endpoints delegate to TickerRepository and return Pydantic
             response models so FastAPI generates accurate OpenAPI types for
             the frontend schema.d.ts auto-generation step.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; search and detail endpoints.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.ticker import Ticker
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


class TickerSearchResponse(BaseModel):
    """Paginated response wrapper for the search endpoint."""

    results: list[TickerSearchResult]
    total: int


# ── Helpers ───────────────────────────────────────────────────────────────────


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
    repo = TickerRepository(db)
    ticker = await repo.get_by_symbol(symbol)
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker not found: '{symbol.upper()}'")
    return _to_result(ticker)
