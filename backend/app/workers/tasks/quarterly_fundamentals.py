"""
Description: Celery task that fetches and upserts the latest fundamental
             snapshot for all active tickers tracked in the database.
             Registered on the beat schedule to run every Monday at 07:00 UTC.
             Weekly cadence is chosen to capture earnings-window updates
             promptly without hammering the yfinance unofficial API.
             Each ticker is processed independently; a ProviderError on one
             symbol is logged and skipped so the whole batch does not abort.
             AsyncSessionLocal is imported lazily inside the async helper to
             avoid triggering _build_engine() at import time (DATABASE_URL is
             not available in unit-test processes).
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; run_quarterly_fundamentals task.
    2026-06-12 - Added annual financial-statement ingest alongside the TTM snapshot.
"""

import asyncio
from datetime import date
from decimal import Decimal

import structlog

from app.data_providers.exceptions import ProviderError
from app.data_providers.yfinance_provider import YFinanceProvider
from app.repositories.financial_statement_repository import (
    FinancialStatementCreate,
    FinancialStatementRepository,
)
from app.repositories.fundamentals_repository import FundamentalsCreate, FundamentalsRepository
from app.repositories.ticker_repository import TickerRepository
from app.workers.celery_app import celery_app

_log = structlog.get_logger(__name__)


def _to_decimal(value: float | None) -> Decimal | None:
    """Convert a provider float to Decimal, returning None if the value is None."""
    return Decimal(str(value)) if value is not None else None


async def _ingest_quarterly_fundamentals() -> None:
    """Fetch and persist today's fundamental snapshot for all active tickers."""
    from app.core.db import AsyncSessionLocal  # noqa: PLC0415

    as_of = date.today()
    provider = YFinanceProvider()

    async with AsyncSessionLocal() as session:
        tickers = await TickerRepository(session).get_all_active()
        fund_repo = FundamentalsRepository(session)
        stmt_repo = FinancialStatementRepository(session)

        for ticker in tickers:
            try:
                dto = await provider.get_fundamentals(ticker.symbol)
                snapshot = FundamentalsCreate(
                    ticker_id=ticker.id,
                    as_of=as_of,
                    market_cap=dto.market_cap,
                    pe_ratio=_to_decimal(dto.pe_ratio),
                    pb_ratio=_to_decimal(dto.pb_ratio),
                    ps_ratio=_to_decimal(dto.ps_ratio),
                    ev_ebitda=_to_decimal(dto.ev_ebitda),
                    eps_ttm=_to_decimal(dto.eps_ttm),
                    revenue_ttm=dto.revenue_ttm,
                    net_income_ttm=dto.net_income_ttm,
                    roe=_to_decimal(dto.roe),
                    debt_to_equity=_to_decimal(dto.debt_to_equity),
                    dividend_yield=_to_decimal(dto.dividend_yield),
                    beta=_to_decimal(dto.beta),
                    week_52_high=_to_decimal(dto.week_52_high),
                    week_52_low=_to_decimal(dto.week_52_low),
                )
                await fund_repo.upsert(snapshot)
                _log.info("quarterly_fundamentals.ingested", symbol=ticker.symbol)
            except ProviderError as exc:
                _log.warning(
                    "quarterly_fundamentals.provider_error",
                    symbol=ticker.symbol,
                    error=str(exc),
                )

            # Annual statements — fetched separately so a failure here doesn't
            # roll back the TTM snapshot already written above.
            try:
                annual_stmts = await provider.get_annual_financials(ticker.symbol)
                for annual in annual_stmts:
                    stmt_create = FinancialStatementCreate(
                        ticker_id=ticker.id,
                        fiscal_year=annual.fiscal_year,
                        currency=annual.currency,
                        total_revenue=annual.total_revenue,
                        gross_profit=annual.gross_profit,
                        operating_income=annual.operating_income,
                        net_income=annual.net_income,
                        interest_expense=annual.interest_expense,
                        eps_diluted=_to_decimal(annual.eps_diluted),
                        total_assets=annual.total_assets,
                        total_equity=annual.total_equity,
                        total_debt=annual.total_debt,
                        cash_and_equivalents=annual.cash_and_equivalents,
                        operating_cash_flow=annual.operating_cash_flow,
                        capital_expenditure=annual.capital_expenditure,
                        shares_diluted=annual.shares_diluted,
                    )
                    await stmt_repo.upsert(stmt_create)
                if annual_stmts:
                    _log.info(
                        "quarterly_fundamentals.statements_ingested",
                        symbol=ticker.symbol,
                        years=len(annual_stmts),
                    )
            except ProviderError as exc:
                _log.warning(
                    "quarterly_fundamentals.statements_provider_error",
                    symbol=ticker.symbol,
                    error=str(exc),
                )

        await session.commit()


@celery_app.task(name="app.workers.tasks.quarterly_fundamentals.run_quarterly_fundamentals")
def run_quarterly_fundamentals() -> None:
    """Celery entry point: upsert today's fundamental snapshot for all active tickers."""
    asyncio.run(_ingest_quarterly_fundamentals())
