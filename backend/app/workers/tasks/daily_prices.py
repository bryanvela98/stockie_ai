"""
Description: Celery task that fetches and upserts yesterday's OHLCV bars
             for all active tickers tracked in the database.
             Registered on the beat schedule to run daily at 18:00 UTC —
             after US market close, before extended-hours data may shift.
             Each ticker is processed independently; a ProviderError on one
             symbol is logged and skipped so the whole batch does not abort.
             AsyncSessionLocal is imported lazily inside the async helper to
             avoid triggering _build_engine() at import time (DATABASE_URL is
             not available in unit-test processes).
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; run_daily_prices task (Sprint 2-B Task 4).
"""

import asyncio
from datetime import date, timedelta

import structlog

from app.data_providers.exceptions import ProviderError
from app.data_providers.yfinance_provider import YFinanceProvider
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository
from app.workers.celery_app import celery_app

_log = structlog.get_logger(__name__)


async def _ingest_daily_prices() -> None:
    """Fetch and persist yesterday's OHLCV bars for all active tickers."""
    # Lazy import keeps _build_engine() from running when this module is
    # imported in test processes where DATABASE_URL is not set.
    from app.core.db import AsyncSessionLocal  # noqa: PLC0415

    yesterday = date.today() - timedelta(days=1)
    today = date.today()
    provider = YFinanceProvider()

    async with AsyncSessionLocal() as session:
        tickers = await TickerRepository(session).get_all_active()
        price_repo = PriceRepository(session)

        for ticker in tickers:
            try:
                bars = await provider.get_price_bars(
                    ticker.symbol,
                    start=yesterday,
                    end=today,
                    interval="1d",
                )
                count = await price_repo.upsert_bars(ticker.id, bars, interval="1d")
                _log.info(
                    "daily_prices.ingested",
                    symbol=ticker.symbol,
                    bars=len(bars),
                    inserted=count,
                )
            except ProviderError as exc:
                _log.warning(
                    "daily_prices.provider_error",
                    symbol=ticker.symbol,
                    error=str(exc),
                )

        await session.commit()


@celery_app.task(name="app.workers.tasks.daily_prices.run_daily_prices")
def run_daily_prices() -> None:
    """Celery entry point: fetch yesterday's OHLCV for all active tickers."""
    asyncio.run(_ingest_daily_prices())
