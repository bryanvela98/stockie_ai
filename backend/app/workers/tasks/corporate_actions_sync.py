"""
Description: Celery task that syncs corporate-action history (splits and dividends)
             for all active tickers and recomputes adjusted_close on price_bars
             rows that are affected by newly inserted splits.
             Registered on the beat schedule to run every Monday at 06:00 UTC,
             before the quarterly_fundamentals task fires at 07:00.
             Recomputation is triggered only for *newly inserted* splits —
             running the UPDATE on an already-adjusted row would compound the
             division. This is tracked by diffing the set of (action_type, ex_date)
             tuples before and after the upsert batch.
             AsyncSessionLocal is imported lazily inside the async helper to
             avoid triggering _build_engine() at import time.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; run_corporate_actions_sync task (Sprint 2-B Task 6).
"""

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import ProviderError
from app.data_providers.yfinance_provider import YFinanceProvider
from app.models.price_bar import PriceBar as PriceBarModel
from app.repositories.corporate_action_repository import (
    ACTION_TYPE_SPLIT,
    CorporateActionCreate,
    CorporateActionRepository,
)
from app.repositories.ticker_repository import TickerRepository
from app.workers.celery_app import celery_app

_log = structlog.get_logger(__name__)


async def _recompute_adjusted_close(
    session: AsyncSession,
    ticker_id: int,
    ex_date_utc: datetime,
    split_ratio: object,
) -> int:
    """Bulk-update adjusted_close for all price_bars before the split ex_date.

    Divides COALESCE(adjusted_close, close) by split_ratio for every row
    where ticker_id matches and timestamp is strictly before ex_date_utc.

    Args:
        session: Open AsyncSession.
        ticker_id: The ticker whose historical bars need adjusting.
        ex_date_utc: Midnight UTC on the ex_date — only bars before this
            timestamp are updated.
        split_ratio: The split ratio to divide by (e.g. Decimal('2.0')).

    Returns:
        Number of rows updated.
    """
    result = await session.execute(
        update(PriceBarModel)
        .where(
            PriceBarModel.ticker_id == ticker_id,
            PriceBarModel.timestamp < ex_date_utc,
        )
        .values(
            adjusted_close=func.coalesce(PriceBarModel.adjusted_close, PriceBarModel.close)
            / split_ratio
        )
        .execution_options(synchronize_session=False)
    )
    return result.rowcount  # type: ignore[attr-defined, no-any-return]


async def _sync_corporate_actions() -> None:
    """Sync corporate actions and recompute adjusted_close for new splits."""
    from app.core.db import AsyncSessionLocal  # noqa: PLC0415

    provider = YFinanceProvider()

    async with AsyncSessionLocal() as session:
        tickers = await TickerRepository(session).get_all_active()
        corp_repo = CorporateActionRepository(session)

        for ticker in tickers:
            try:
                actions = await provider.get_corporate_actions(ticker.symbol)
            except ProviderError as exc:
                _log.warning(
                    "corporate_actions_sync.provider_error",
                    symbol=ticker.symbol,
                    error=str(exc),
                )
                continue

            # Snapshot existing (action_type, ex_date) keys before upsert so
            # we can detect which splits are genuinely new and need recomputation.
            existing = await corp_repo.get_by_ticker(ticker.id)
            existing_keys = {(a.action_type, a.ex_date) for a in existing}

            for dto in actions:
                action_create = CorporateActionCreate(
                    ticker_id=ticker.id,
                    action_type=dto.action_type,
                    ex_date=dto.ex_date,
                    ratio=dto.ratio,
                )
                await corp_repo.upsert(action_create)

                is_new = (dto.action_type, dto.ex_date) not in existing_keys
                if is_new and dto.action_type == ACTION_TYPE_SPLIT:
                    ex_date_utc = datetime(
                        dto.ex_date.year,
                        dto.ex_date.month,
                        dto.ex_date.day,
                        tzinfo=UTC,
                    )
                    updated = await _recompute_adjusted_close(
                        session, ticker.id, ex_date_utc, dto.ratio
                    )
                    _log.info(
                        "corporate_actions_sync.split_adjusted",
                        symbol=ticker.symbol,
                        ex_date=str(dto.ex_date),
                        ratio=str(dto.ratio),
                        rows_updated=updated,
                    )

            _log.info(
                "corporate_actions_sync.synced",
                symbol=ticker.symbol,
                actions=len(actions),
            )

        await session.commit()


@celery_app.task(name="app.workers.tasks.corporate_actions_sync.run_corporate_actions_sync")
def run_corporate_actions_sync() -> None:
    """Celery entry point: sync corporate actions and adjust historical prices."""
    asyncio.run(_sync_corporate_actions())
