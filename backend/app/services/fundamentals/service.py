"""
Description: FundamentalsService — orchestrates the full fundamental analysis
             pipeline for a single ticker and serves results from a Redis
             cache (daily TTL) when available.

             Flow:
               1. Cache lookup  → return if hit
               2. Resolve ticker (TickerRepository)
               3. Load latest Fundamentals snapshot
               4. Load annual FinancialStatement history (≤ 6 rows)
               5. Run Plan-A calculators: ratios, quality, growth
               6. score_fundamental() → FundamentalScore
               7. Assemble FundamentalsResult, write to cache, return

             Cache key: `fundamentals:v{WEIGHTS_VERSION}:{symbol}:{as_of}`
             A WEIGHTS_VERSION bump automatically invalidates stale scores.

             Raises TickerNotFoundError when the symbol is unknown or has no
             fundamentals snapshot yet — the router maps this to HTTP 404.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; FundamentalsResult dataclass + FundamentalsService.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.data_providers.exceptions import TickerNotFoundError
from app.models.financial_statement import PERIOD_TYPE_ANNUAL
from app.repositories.financial_statement_repository import FinancialStatementRepository
from app.repositories.fundamentals_repository import FundamentalsRepository
from app.repositories.ticker_repository import TickerRepository
from app.scoring.fundamental import WEIGHTS_VERSION, FundamentalScore, score_fundamental
from app.services.fundamentals.growth import GrowthMetrics, compute_growth_metrics
from app.services.fundamentals.quality import (
    QualityMetrics,
    compute_quality_metrics,
)
from app.services.fundamentals.quality import (
    debt_to_equity as _de,
)
from app.services.fundamentals.quality import (
    roe as _roe,
)
from app.services.fundamentals.ratios import ValuationRatios, compute_valuation_ratios

CACHE_TTL_SECONDS = 86_400  # 1 day


@dataclass(frozen=True)
class FundamentalsResult:
    """Assembled fundamental analysis result for a single ticker.

    All sub-objects are frozen dataclasses; the `to_dict()` / `from_dict()`
    pair is used for Redis JSON serialisation.
    """

    symbol: str
    data_as_of: date
    weights_version: str

    # Raw metrics
    ratios: ValuationRatios
    quality: QualityMetrics
    growth: GrowthMetrics

    # Scores (0–100 or None)
    score: FundamentalScore

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialise to a plain dict suitable for JSON encoding."""
        d = asdict(self)
        d["data_as_of"] = self.data_as_of.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> FundamentalsResult:  # type: ignore[type-arg]
        """Reconstruct from a plain dict (deserialised from JSON cache)."""
        return cls(
            symbol=d["symbol"],
            data_as_of=date.fromisoformat(d["data_as_of"]),
            weights_version=d["weights_version"],
            ratios=ValuationRatios(**d["ratios"]),
            quality=QualityMetrics(**d["quality"]),
            growth=GrowthMetrics(**d["growth"]),
            score=FundamentalScore(**d["score"]),
        )


class FundamentalsService:
    """Assembles the full fundamental analysis payload for a ticker.

    Instantiate with an open AsyncSession; the session is used by the
    repository layer. Cache I/O is performed via the module-level async
    helpers in `app.core.cache`.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an open async database session.

        Args:
            session: Active AsyncSession for repository queries.
        """
        self._session = session
        self._ticker_repo = TickerRepository(session)
        self._fund_repo = FundamentalsRepository(session)
        self._stmt_repo = FinancialStatementRepository(session)

    async def get_fundamentals(self, symbol: str) -> FundamentalsResult:
        """Return the assembled fundamental analysis for a ticker.

        Checks the Redis cache first. On a miss, reads from the DB, runs all
        calculators, scores the result, writes to cache, and returns.

        Args:
            symbol: Ticker symbol (case-insensitive, normalised to upper-case).

        Returns:
            A FundamentalsResult containing ratios, quality, growth, and scores.

        Raises:
            TickerNotFoundError: When the symbol is unknown or has no snapshot.
        """
        symbol = symbol.upper()

        # ── 1. Cache lookup ───────────────────────────────────────────────────
        ticker = await self._ticker_repo.get_by_symbol(symbol)
        if ticker is None:
            raise TickerNotFoundError(f"Ticker not found: {symbol}")

        snapshot = await self._fund_repo.get_latest(ticker.id)
        if snapshot is None:
            raise TickerNotFoundError(f"No fundamental snapshot for: {symbol}")

        cache_key = f"fundamentals:v{WEIGHTS_VERSION}:{symbol}:{snapshot.as_of.isoformat()}"
        cached = await cache.get_json(cache_key)
        if cached is not None:
            return FundamentalsResult.from_dict(cached)

        # ── 2. Load annual statements ─────────────────────────────────────────
        stmts = await self._stmt_repo.get_history(
            ticker.id, period_type=PERIOD_TYPE_ANNUAL, limit=6
        )

        # ── 3. Run calculators ────────────────────────────────────────────────
        ratios = compute_valuation_ratios(snapshot)

        if stmts:
            quality = compute_quality_metrics(stmts[0], snapshot=snapshot)
            growth = compute_growth_metrics(stmts)
        else:
            # No annual statements yet — derive what we can from the snapshot alone.
            quality = QualityMetrics(
                roe=_roe(snapshot),
                roic=None,
                gross_margin=None,
                operating_margin=None,
                net_margin=None,
                debt_to_equity=_de(snapshot=snapshot),
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

        # ── 4. Score ──────────────────────────────────────────────────────────
        score = score_fundamental(ratios, quality, growth)

        # ── 5. Assemble + cache ───────────────────────────────────────────────
        result = FundamentalsResult(
            symbol=symbol,
            data_as_of=snapshot.as_of,
            weights_version=WEIGHTS_VERSION,
            ratios=ratios,
            quality=quality,
            growth=growth,
            score=score,
        )
        await cache.set_json(cache_key, result.to_dict(), ttl=CACHE_TTL_SECONDS)
        return result
