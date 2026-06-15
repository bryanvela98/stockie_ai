"""
Description: Tests for the DCF calculator service in app.services.fundamentals.dcf.
             Verifies the pure _compute_dcf() math with a hand-computed golden
             fixture, and the DcfService DB-access paths.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; golden DCF computation and guardrail tests.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.data_providers.models import TickerInfo
from app.repositories.financial_statement_repository import (
    FinancialStatementCreate,
    FinancialStatementRepository,
)
from app.repositories.ticker_repository import TickerRepository
from app.services.fundamentals.dcf import DcfService, _compute_dcf

# ── pure math tests ───────────────────────────────────────────────────────────


def test_compute_dcf_golden_values() -> None:
    """Hand-computed 3-year DCF with known inputs.

    Base FCF = 100, growth = 10 %, discount = 12 %, terminal growth = 3 %,
    years = 3, net_debt = 0, shares = 10.

    Year 1: FCF = 110, PV = 110/1.12 = 98.21
    Year 2: FCF = 121, PV = 121/1.12^2 = 96.47
    Year 3: FCF = 133.1, PV = 133.1/1.12^3 = 94.76
    Sum = 289.44
    TV = 133.1*1.03/(0.12-0.03) = 137.093/0.09 = 1523.26
    PV(TV) = 1523.26/1.12^3 = 1083.96
    EV = 289.44 + 1083.96 = 1373.40
    Equity = EV - 0 = 1373.40
    Per share = 1373.40/10 = 137.34
    """
    ev, equity, tv, per_share, yearly = _compute_dcf(
        base_fcf=100.0,
        shares_diluted=10.0,
        net_debt=0.0,
        growth_rate=0.10,
        discount_rate=0.12,
        terminal_growth=0.03,
        years=3,
    )
    assert ev == pytest.approx(1373.40, rel=1e-3)
    assert equity == pytest.approx(1373.40, rel=1e-3)
    assert tv == pytest.approx(1523.26, rel=1e-3)
    assert per_share == pytest.approx(137.34, rel=1e-3)
    assert len(yearly) == 3
    assert yearly[0].year == 1
    assert yearly[0].projected_fcf == pytest.approx(110.0, rel=1e-4)


def test_compute_dcf_negative_net_debt_increases_equity() -> None:
    """Negative net_debt (cash-rich company) increases equity value above EV."""
    ev, equity, tv, per_share, _ = _compute_dcf(
        base_fcf=100.0,
        shares_diluted=10.0,
        net_debt=-50.0,  # company has more cash than debt
        growth_rate=0.05,
        discount_rate=0.10,
        terminal_growth=0.02,
        years=3,
    )
    assert equity > ev
    assert equity == pytest.approx(ev + 50.0, rel=1e-6)


def test_compute_dcf_per_share_none_when_no_shares() -> None:
    """per_share is None when shares_diluted = 0."""
    _, _, _, per_share, _ = _compute_dcf(
        base_fcf=100.0,
        shares_diluted=0.0,
        net_debt=0.0,
        growth_rate=0.05,
        discount_rate=0.10,
        terminal_growth=0.02,
        years=3,
    )
    assert per_share is None


# ── DcfService tests ──────────────────────────────────────────────────────────


async def _seed(session: AsyncSession) -> None:
    """Seed one ticker + one annual statement."""
    ticker_repo = TickerRepository(session)
    ticker = await ticker_repo.upsert(
        TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_type="equity",
            currency="USD",
        )
    )
    stmt_repo = FinancialStatementRepository(session)
    await stmt_repo.upsert(
        FinancialStatementCreate(
            ticker_id=ticker.id,
            fiscal_year=2024,
            operating_cash_flow=118_254_000_000,
            capital_expenditure=-9_447_000_000,
            total_debt=96_630_000_000,
            cash_and_equivalents=65_170_000_000,
            shares_diluted=15_408_000_000,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_dcf_service_raises_on_unknown_ticker(db_session: AsyncSession) -> None:
    """DcfService raises TickerNotFoundError when symbol is absent."""
    service = DcfService(db_session)
    with pytest.raises(TickerNotFoundError):
        await service.compute("ZZZZ", 0.08, 0.10, 0.03, 5)


@pytest.mark.asyncio
async def test_dcf_service_raises_on_no_statements(db_session: AsyncSession) -> None:
    """DcfService raises TickerNotFoundError when no annual statements exist."""
    repo = TickerRepository(db_session)
    await repo.upsert(
        TickerInfo(
            symbol="BARE", name="No Data Inc.", exchange="NYSE", asset_type="equity", currency="USD"
        )
    )
    await db_session.commit()
    service = DcfService(db_session)
    with pytest.raises(TickerNotFoundError):
        await service.compute("BARE", 0.08, 0.10, 0.03, 5)


@pytest.mark.asyncio
async def test_dcf_service_returns_result(db_session: AsyncSession) -> None:
    """DcfService returns a DcfResult with plausible values for AAPL-like data."""
    await _seed(db_session)
    service = DcfService(db_session)
    result = await service.compute("AAPL", 0.08, 0.10, 0.03, 5)

    assert result.symbol == "AAPL"
    assert result.intrinsic_value_per_share is not None
    assert result.intrinsic_value_per_share > 0
    assert len(result.yearly_fcf) == 5
    assert result.assumptions["growth_rate"] == 0.08
    assert result.assumptions["discount_rate"] == 0.10


@pytest.mark.asyncio
async def test_dcf_service_echoes_base_fcf_in_assumptions(db_session: AsyncSession) -> None:
    """DcfResult.assumptions includes base_fcf = OCF + capex."""
    await _seed(db_session)
    service = DcfService(db_session)
    result = await service.compute("AAPL", 0.08, 0.10, 0.03, 5)

    expected_base_fcf = 118_254_000_000 + (-9_447_000_000)
    assert result.assumptions["base_fcf"] == pytest.approx(expected_base_fcf, rel=1e-6)
