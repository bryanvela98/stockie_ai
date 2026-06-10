"""
Description: One-shot CLI script to backfill N years of daily OHLCV history
             for all tracked tickers (or an explicit subset).
             Reads DATABASE_URL from the environment via AppSettings.
             Upsert logic is idempotent — re-running the script with the same
             arguments is safe and will not create duplicate rows.
             Usage:
               uv run python scripts/backfill.py --years 5
               uv run python scripts/backfill.py --symbols AAPL,MSFT --years 2
               uv run python scripts/backfill.py --symbols AAPL --years 2 --dry-run
             Options:
               --years N       Number of calendar years of history to load (default: 5).
               --symbols A,B   Comma-separated list of symbols to restrict the run.
                               If omitted, all active tickers in the database are used.
               --dry-run       Print what would be fetched without writing to the DB.
               --delay SECS    Seconds to sleep between ticker requests (default: 0.5).
                               Helps avoid yfinance rate-limiting on large universes.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; backfill CLI script (Sprint 2-B Task 7).
"""

import argparse
import asyncio
import time
from datetime import date

import structlog

from app.core.logging import configure_logging

configure_logging()
_log = structlog.get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill historical OHLCV data for tracked tickers."
    )
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        metavar="N",
        help="Number of calendar years of history to load (default: 5).",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        metavar="A,B,C",
        help="Comma-separated ticker symbols to restrict the run. "
        "If omitted, all active tickers in the database are used.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without writing to the database.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        metavar="SECS",
        help="Seconds to sleep between ticker requests (default: 0.5).",
    )
    return parser.parse_args()


async def _run_backfill(
    symbols: list[str] | None,
    years: int,
    dry_run: bool,
    delay: float,
) -> None:
    """Core backfill logic: fetch and upsert OHLCV history for each ticker.

    Args:
        symbols: Explicit list of symbols to process, or None to use all active
                 tickers from the database.
        years: Number of calendar years of history to load.
        dry_run: When True, log the plan and skip DB writes.
        delay: Seconds to sleep between ticker requests.
    """
    from app.core.db import AsyncSessionLocal  # noqa: PLC0415
    from app.data_providers.exceptions import ProviderError  # noqa: PLC0415
    from app.data_providers.yfinance_provider import YFinanceProvider  # noqa: PLC0415
    from app.repositories.price_repository import PriceRepository  # noqa: PLC0415
    from app.repositories.ticker_repository import TickerRepository  # noqa: PLC0415

    end = date.today()
    start = date(end.year - years, end.month, end.day)

    provider = YFinanceProvider()

    if symbols is not None:
        _log.info(
            "backfill.start", mode="explicit", symbols=symbols, start=str(start), end=str(end)
        )
        ticker_symbols = symbols
    else:
        async with AsyncSessionLocal() as session:
            tickers = await TickerRepository(session).get_all_active()
        ticker_symbols = [t.symbol for t in tickers]
        _log.info(
            "backfill.start",
            mode="all_active",
            count=len(ticker_symbols),
            start=str(start),
            end=str(end),
        )

    if dry_run:
        _log.info(
            "backfill.dry_run",
            tickers=ticker_symbols,
            start=str(start),
            end=str(end),
            years=years,
        )
        return

    total_inserted = 0

    for symbol in ticker_symbols:
        try:
            bars = await provider.get_price_bars(symbol, start=start, end=end, interval="1d")
            _log.info("backfill.fetched", symbol=symbol, bars=len(bars))

            async with AsyncSessionLocal() as session:
                ticker_repo = TickerRepository(session)
                ticker = await ticker_repo.get_by_symbol(symbol)
                if ticker is None:
                    _log.warning("backfill.ticker_not_found", symbol=symbol)
                    continue

                price_repo = PriceRepository(session)
                inserted = await price_repo.upsert_bars(ticker.id, bars, interval="1d")
                await session.commit()

            total_inserted += inserted
            _log.info("backfill.upserted", symbol=symbol, inserted=inserted, total_bars=len(bars))

        except ProviderError as exc:
            _log.warning("backfill.provider_error", symbol=symbol, error=str(exc))

        if delay > 0:
            time.sleep(delay)

    _log.info("backfill.complete", total_inserted=total_inserted)


def main() -> None:
    """Entry point — parse CLI args and run the async backfill."""
    args = _parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None

    if args.dry_run:
        end = date.today()
        start = date(end.year - args.years, end.month, end.day)
        target = symbols or ["<all active tickers from DB>"]
        print(f"DRY RUN — would fetch {args.years}y of daily bars")  # noqa: T201
        print(f"  Date range : {start} → {end}")  # noqa: T201
        print(f"  Tickers    : {', '.join(target)}")  # noqa: T201
        print(f"  Delay      : {args.delay}s between requests")  # noqa: T201
        return

    asyncio.run(
        _run_backfill(
            symbols=symbols,
            years=args.years,
            dry_run=args.dry_run,
            delay=args.delay,
        )
    )


if __name__ == "__main__":
    main()
