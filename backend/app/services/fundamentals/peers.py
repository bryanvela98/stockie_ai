"""
Description: Peer-comparison service for Stockie AI.
             Selects 3–5 same-sector peers for a given ticker, ranked by
             market-cap proximity, and returns headline ratios + overall score.

             Market-cap bucket thresholds (USD):
               mega  : >= 200_000_000_000  ($200B+)
               large :   10_000_000_000 – 200_000_000_000  ($10B–$200B)
               mid   :    2_000_000_000 –  10_000_000_000  ($2B–$10B)
               small :  <  2_000_000_000  (below $2B)

             Ranking: |log(market_cap_peer) - log(market_cap_subject)|.
             Tickers with no market_cap are sorted last. The subject itself
             is never included in the result.

             When the sector is null or the sector has fewer than the requested
             peers, all available same-sector tickers are returned (may be < 3).
             This is a 200 OK with an empty list, not an error.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; PeerEntry, PeerService with bucket-ranked selection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.models.ticker import Ticker
from app.repositories.fundamentals_repository import FundamentalsRepository
from app.repositories.ticker_repository import TickerRepository
from app.scoring.fundamental import score_fundamental
from app.services.fundamentals.growth import GrowthMetrics
from app.services.fundamentals.quality import QualityMetrics
from app.services.fundamentals.quality import debt_to_equity as _de
from app.services.fundamentals.quality import roe as _roe
from app.services.fundamentals.ratios import compute_valuation_ratios

# Market-cap bucket boundaries in USD
_MEGA_CAP = 200_000_000_000
_LARGE_CAP = 10_000_000_000
_MID_CAP = 2_000_000_000


def _bucket(market_cap: int) -> int:
    """Map a market cap to a numeric bucket index (higher = larger).

    Args:
        market_cap: Market capitalisation in USD.

    Returns:
        3 = mega, 2 = large, 1 = mid, 0 = small.
    """
    if market_cap >= _MEGA_CAP:
        return 3
    if market_cap >= _LARGE_CAP:
        return 2
    if market_cap >= _MID_CAP:
        return 1
    return 0


def _proximity_score(subject_cap: int | None, peer_cap: int | None) -> float:
    """Return a proximity score (lower = closer in size).

    Uses |log(peer_cap) - log(subject_cap)| so relative differences are
    scale-invariant. Tickers with no market_cap receive +inf (sorted last).

    Args:
        subject_cap: Market cap of the subject ticker (may be None).
        peer_cap: Market cap of the candidate peer (may be None).

    Returns:
        Non-negative float proximity score.
    """
    if subject_cap is None or peer_cap is None or subject_cap <= 0 or peer_cap <= 0:
        return float("inf")
    return abs(math.log(peer_cap) - math.log(subject_cap))


@dataclass(frozen=True)
class PeerEntry:
    """Headline data for a single peer ticker."""

    symbol: str
    name: str
    market_cap: int | None
    pe: float | None
    pb: float | None
    ps: float | None
    ev_ebitda: float | None
    dividend_yield: float | None
    overall_score: float | None


class PeerService:
    """Selects and scores same-sector peers for a ticker.

    Raises TickerNotFoundError when the subject symbol is unknown.
    Returns an empty list (not an error) when the sector is null or
    no peers are available.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an open async database session.

        Args:
            session: Active AsyncSession for repository queries.
        """
        self._session = session
        self._ticker_repo = TickerRepository(session)
        self._fund_repo = FundamentalsRepository(session)

    async def get_peers(self, symbol: str, limit: int = 5) -> list[PeerEntry]:
        """Return ranked same-sector peers for a ticker.

        Args:
            symbol: Subject ticker symbol (case-insensitive).
            limit: Maximum number of peers to return.

        Returns:
            List of PeerEntry objects ordered by market-cap proximity.

        Raises:
            TickerNotFoundError: When the symbol does not exist in the DB.
        """
        symbol = symbol.upper()
        ticker = await self._ticker_repo.get_by_symbol(symbol)
        if ticker is None:
            raise TickerNotFoundError(f"Ticker not found: {symbol}")

        if not ticker.sector:
            return []

        # Latest snapshot for the subject (to get market_cap)
        subject_snapshot = await self._fund_repo.get_latest(ticker.id)
        subject_cap: int | None = subject_snapshot.market_cap if subject_snapshot else None

        candidates = await self._ticker_repo.get_by_sector(ticker.sector, exclude_id=ticker.id)
        if not candidates:
            return []

        # Build (ticker, market_cap, proximity) tuples then sort properly
        peer_caps: list[tuple[int | None, float, Ticker]] = []
        for candidate in candidates:
            snap = await self._fund_repo.get_latest(candidate.id)
            cap = snap.market_cap if snap else None
            peer_caps.append((cap, _proximity_score(subject_cap, cap), candidate))

        peer_caps.sort(key=lambda x: x[1])
        top = peer_caps[:limit]

        entries: list[PeerEntry] = []
        for cap, _prox, candidate in top:
            snap = await self._fund_repo.get_latest(candidate.id)
            if snap is not None:
                ratios = compute_valuation_ratios(snap)
                # Snapshot-only quality — no annual statements needed for peer headline scoring
                quality = QualityMetrics(
                    roe=_roe(snap),
                    roic=None,
                    gross_margin=None,
                    operating_margin=None,
                    net_margin=None,
                    debt_to_equity=_de(snapshot=snap),
                    interest_coverage=None,
                )
                growth = GrowthMetrics(
                    revenue_cagr_1y=None,
                    revenue_cagr_3y=None,
                    revenue_cagr_5y=None,
                    revenue_years_used_5y=None,
                    eps_cagr_1y=None,
                    eps_cagr_3y=None,
                    eps_cagr_5y=None,
                    eps_years_used_5y=None,
                    fcf_cagr_1y=None,
                    fcf_cagr_3y=None,
                    fcf_cagr_5y=None,
                    fcf_years_used_5y=None,
                )
                score = score_fundamental(ratios, quality, growth)
                overall = score.overall
            else:
                ratios = None
                overall = None

            entries.append(
                PeerEntry(
                    symbol=candidate.symbol,
                    name=candidate.name,
                    market_cap=cap,
                    pe=ratios.pe if ratios else None,
                    pb=ratios.pb if ratios else None,
                    ps=ratios.ps if ratios else None,
                    ev_ebitda=ratios.ev_ebitda if ratios else None,
                    dividend_yield=ratios.dividend_yield if ratios else None,
                    overall_score=overall,
                )
            )

        return entries
