"""
Description: Fundamentals API router for Stockie AI.
             Exposes three endpoints under /tickers/{symbol}:

               GET /tickers/{symbol}/fundamentals
                   Full fundamental analysis: valuation ratios, quality metrics,
                   growth CAGRs, and Value/Quality/Growth subscores + overall.
                   Results are Redis-cached with a daily TTL by FundamentalsService.

               GET /tickers/{symbol}/dcf
                   Simplified 2-stage DCF with adjustable assumptions passed as
                   query params so the frontend widget recalculates live.

               GET /tickers/{symbol}/peers
                   3–5 auto-selected peers from the same sector ranked by
                   market-cap proximity, each with headline ratios + overall score.

             All response schemas defined here are the frozen contract for the
             frontend Plan-C build. Do not rename or remove fields without
             updating the frontend schema.d.ts.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; fundamentals endpoint + Pydantic response models.
    2026-06-13 - Added DCF endpoint and peer-comparison endpoint.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.data_providers.exceptions import TickerNotFoundError
from app.services.fundamentals.dcf import DcfService
from app.services.fundamentals.peers import PeerService
from app.services.fundamentals.service import FundamentalsService

router = APIRouter(tags=["fundamentals"])
_log = structlog.get_logger(__name__)


# ── Response models ───────────────────────────────────────────────────────────


class RatioBlock(BaseModel):
    """Valuation ratios for a ticker.

    All fields are Optional — a ratio is None when the required inputs
    (e.g. earnings, book value) are unavailable.
    """

    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    ev_ebitda: float | None = None
    dividend_yield: float | None = None
    peg: float | None = None


class QualityBlock(BaseModel):
    """Profitability, safety, and efficiency metrics for a ticker."""

    roe: float | None = None
    roic: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None


class GrowthBlock(BaseModel):
    """Revenue, EPS, and FCF CAGR metrics for a ticker."""

    revenue_cagr_1y: float | None = None
    revenue_cagr_3y: float | None = None
    revenue_cagr_5y: float | None = None
    revenue_years_used_5y: int | None = None
    eps_cagr_1y: float | None = None
    eps_cagr_3y: float | None = None
    eps_cagr_5y: float | None = None
    eps_years_used_5y: int | None = None
    fcf_cagr_1y: float | None = None
    fcf_cagr_3y: float | None = None
    fcf_cagr_5y: float | None = None
    fcf_years_used_5y: int | None = None


class SubscoreBlock(BaseModel):
    """Fundamental subscores on a 0–100 scale (or null when no data)."""

    overall: float | None = None
    value: float | None = None
    quality: float | None = None
    growth: float | None = None
    weights_version: str


class FundamentalsResponse(BaseModel):
    """Full fundamental analysis payload for a single ticker."""

    symbol: str
    data_as_of: date
    ratios: RatioBlock
    quality: QualityBlock
    growth: GrowthBlock
    scores: SubscoreBlock


class DcfYearItem(BaseModel):
    """Projected and discounted FCF for a single year of the DCF model."""

    year: int
    projected_fcf: float
    discounted_fcf: float


class DcfResponse(BaseModel):
    """Simplified 2-stage DCF output."""

    symbol: str
    intrinsic_value_per_share: float | None = None
    enterprise_value: float
    equity_value: float
    terminal_value: float
    assumptions: dict[str, float]
    yearly_fcf: list[DcfYearItem]


class PeerItem(BaseModel):
    """Headline data for a single peer ticker."""

    symbol: str
    name: str
    market_cap: int | None = None
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    ev_ebitda: float | None = None
    dividend_yield: float | None = None
    overall_score: float | None = None


class PeersResponse(BaseModel):
    """Peer-comparison payload."""

    symbol: str
    peers: list[PeerItem]


# ── Endpoint helpers ──────────────────────────────────────────────────────────


def _not_found(symbol: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Ticker not found: {symbol}")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/{symbol}/fundamentals", response_model=FundamentalsResponse)
async def get_fundamentals(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FundamentalsResponse:
    """Return the full fundamental analysis for a ticker.

    The response includes valuation ratios, quality metrics, growth CAGRs,
    and the Value/Quality/Growth subscores + overall score (all 0–100).
    Results are Redis-cached with a 24-hour TTL.

    Args:
        symbol: Ticker symbol (case-insensitive).
        db: Injected async database session.

    Returns:
        FundamentalsResponse with all metric blocks and scores.

    Raises:
        HTTPException(404): When the symbol is unknown or has no snapshot.
    """
    service = FundamentalsService(db)
    try:
        result = await service.get_fundamentals(symbol)
    except TickerNotFoundError:
        raise _not_found(symbol) from None

    ratios = result.ratios
    quality = result.quality
    growth = result.growth
    score = result.score

    return FundamentalsResponse(
        symbol=result.symbol,
        data_as_of=result.data_as_of,
        ratios=RatioBlock(
            pe=ratios.pe,
            pb=ratios.pb,
            ps=ratios.ps,
            ev_ebitda=ratios.ev_ebitda,
            dividend_yield=ratios.dividend_yield,
            peg=ratios.peg,
        ),
        quality=QualityBlock(
            roe=quality.roe,
            roic=quality.roic,
            gross_margin=quality.gross_margin,
            operating_margin=quality.operating_margin,
            net_margin=quality.net_margin,
            debt_to_equity=quality.debt_to_equity,
            interest_coverage=quality.interest_coverage,
        ),
        growth=GrowthBlock(
            revenue_cagr_1y=growth.revenue_cagr_1y,
            revenue_cagr_3y=growth.revenue_cagr_3y,
            revenue_cagr_5y=growth.revenue_cagr_5y,
            revenue_years_used_5y=growth.revenue_years_used_5y,
            eps_cagr_1y=growth.eps_cagr_1y,
            eps_cagr_3y=growth.eps_cagr_3y,
            eps_cagr_5y=growth.eps_cagr_5y,
            eps_years_used_5y=growth.eps_years_used_5y,
            fcf_cagr_1y=growth.fcf_cagr_1y,
            fcf_cagr_3y=growth.fcf_cagr_3y,
            fcf_cagr_5y=growth.fcf_cagr_5y,
            fcf_years_used_5y=growth.fcf_years_used_5y,
        ),
        scores=SubscoreBlock(
            overall=score.overall,
            value=score.value,
            quality=score.quality,
            growth=score.growth,
            weights_version=score.weights_version,
        ),
    )


@router.get("/{symbol}/dcf", response_model=DcfResponse)
async def get_dcf(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    growth_rate: Annotated[float, Query(ge=0.0, le=1.0)] = 0.08,
    discount_rate: Annotated[float, Query(gt=0.0, lt=1.0)] = 0.10,
    terminal_growth: Annotated[float, Query(ge=0.0, lt=1.0)] = 0.03,
    years: Annotated[int, Query(ge=1, le=15)] = 5,
) -> DcfResponse:
    """Return a simplified 2-stage DCF intrinsic value for a ticker.

    Assumptions are passed as query params so the frontend slider widget
    can call this endpoint live without server-side caching.

    Args:
        symbol: Ticker symbol (case-insensitive).
        db: Injected async database session.
        growth_rate: Near-term FCF growth rate (0–1, default 0.08 = 8 %).
        discount_rate: WACC / discount rate (0–1, default 0.10 = 10 %).
        terminal_growth: Gordon terminal growth rate. Must be < discount_rate.
        years: Number of projection years (1–15, default 5).

    Returns:
        DcfResponse with intrinsic value per share, per-year breakdown, and echoed assumptions.

    Raises:
        HTTPException(400): When terminal_growth >= discount_rate (divergent terminal value).
        HTTPException(404): When the symbol is unknown.
    """
    if terminal_growth >= discount_rate:
        raise HTTPException(
            status_code=400,
            detail="terminal_growth must be strictly less than discount_rate",
        )

    service = DcfService(db)
    try:
        result = await service.compute(
            symbol=symbol,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            terminal_growth=terminal_growth,
            years=years,
        )
    except TickerNotFoundError:
        raise _not_found(symbol) from None

    return DcfResponse(
        symbol=result.symbol,
        intrinsic_value_per_share=result.intrinsic_value_per_share,
        enterprise_value=result.enterprise_value,
        equity_value=result.equity_value,
        terminal_value=result.terminal_value,
        assumptions=result.assumptions,
        yearly_fcf=[
            DcfYearItem(
                year=y.year,
                projected_fcf=y.projected_fcf,
                discounted_fcf=y.discounted_fcf,
            )
            for y in result.yearly_fcf
        ],
    )


@router.get("/{symbol}/peers", response_model=PeersResponse)
async def get_peers(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> PeersResponse:
    """Return same-sector peers ranked by market-cap proximity.

    Args:
        symbol: Ticker symbol (case-insensitive).
        db: Injected async database session.
        limit: Maximum number of peers to return (1–10, default 5).

    Returns:
        PeersResponse with up to `limit` peers, each with headline ratios and overall score.

    Raises:
        HTTPException(404): When the symbol is unknown.
    """
    service = PeerService(db)
    try:
        peers = await service.get_peers(symbol, limit=limit)
    except TickerNotFoundError:
        raise _not_found(symbol) from None

    return PeersResponse(
        symbol=symbol.upper(),
        peers=[
            PeerItem(
                symbol=p.symbol,
                name=p.name,
                market_cap=p.market_cap,
                pe=p.pe,
                pb=p.pb,
                ps=p.ps,
                ev_ebitda=p.ev_ebitda,
                dividend_yield=p.dividend_yield,
                overall_score=p.overall_score,
            )
            for p in peers
        ],
    )
