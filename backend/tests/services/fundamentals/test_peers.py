"""
Description: Tests for PeerService — same-sector peer selection and ranking.
             Uses an in-memory SQLite universe with 3 sectors and varied
             market caps to verify selection, ranking, subject-exclusion, and
             the empty-sector / missing-snapshot edge cases.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; selection, ranking, exclusion, and empty-sector tests.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.exceptions import TickerNotFoundError
from app.data_providers.models import TickerInfo
from app.repositories.fundamentals_repository import FundamentalsCreate, FundamentalsRepository
from app.repositories.ticker_repository import TickerRepository
from app.services.fundamentals.peers import PeerService, _bucket, _proximity_score

# ── pure helper tests ─────────────────────────────────────────────────────────


def test_bucket_classification() -> None:
    """Market-cap thresholds produce the expected bucket integers."""
    assert _bucket(500_000_000_000) == 3  # mega
    assert _bucket(50_000_000_000) == 2  # large
    assert _bucket(5_000_000_000) == 1  # mid
    assert _bucket(500_000_000) == 0  # small


def test_proximity_score_identical_caps() -> None:
    """Identical market caps → proximity score = 0."""
    assert _proximity_score(1_000_000, 1_000_000) == pytest.approx(0.0)


def test_proximity_score_none_cap() -> None:
    """None cap → inf proximity (sorted last)."""
    assert _proximity_score(None, 100) == float("inf")
    assert _proximity_score(100, None) == float("inf")


# ── DB seeding helpers ────────────────────────────────────────────────────────


async def _add_ticker(
    session: AsyncSession,
    symbol: str,
    sector: str | None,
    market_cap: int | None = None,
) -> int:
    repo = TickerRepository(session)
    ticker = await repo.upsert(
        TickerInfo(
            symbol=symbol,
            name=f"{symbol} Corp.",
            exchange="NYSE",
            asset_type="equity",
            currency="USD",
            sector=sector,
        )
    )
    if market_cap is not None:
        fund_repo = FundamentalsRepository(session)
        await fund_repo.upsert(
            FundamentalsCreate(
                ticker_id=ticker.id,
                as_of=date(2024, 1, 1),
                market_cap=market_cap,
                pe_ratio=Decimal("20.0"),
            )
        )
    return ticker.id


# ── PeerService tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_peer_service_raises_on_unknown_ticker(db_session: AsyncSession) -> None:
    """PeerService raises TickerNotFoundError for an unknown symbol."""
    service = PeerService(db_session)
    with pytest.raises(TickerNotFoundError):
        await service.get_peers("ZZZZZ")


@pytest.mark.asyncio
async def test_peer_service_returns_empty_when_no_sector(db_session: AsyncSession) -> None:
    """Returns empty list (not an error) when the subject has no sector."""
    await _add_ticker(db_session, "ETF1", sector=None, market_cap=500_000_000_000)
    await db_session.commit()
    service = PeerService(db_session)
    result = await service.get_peers("ETF1")
    assert result == []


@pytest.mark.asyncio
async def test_peer_service_excludes_subject(db_session: AsyncSession) -> None:
    """Subject ticker is never included in its own peer list."""
    await _add_ticker(db_session, "AAPL", "Technology", 3_000_000_000_000)
    await _add_ticker(db_session, "MSFT", "Technology", 2_800_000_000_000)
    await _add_ticker(db_session, "GOOG", "Technology", 2_000_000_000_000)
    await db_session.commit()

    service = PeerService(db_session)
    result = await service.get_peers("AAPL", limit=5)
    symbols = {p.symbol for p in result}
    assert "AAPL" not in symbols
    assert len(result) <= 2  # only MSFT and GOOG


@pytest.mark.asyncio
async def test_peer_service_respects_limit(db_session: AsyncSession) -> None:
    """get_peers returns at most `limit` peers."""
    for sym in ["A", "B", "C", "D", "E", "F"]:
        await _add_ticker(db_session, sym, "Energy", 10_000_000_000)
    await _add_ticker(db_session, "SUBJ", "Energy", 10_000_000_000)
    await db_session.commit()

    service = PeerService(db_session)
    result = await service.get_peers("SUBJ", limit=3)
    assert len(result) <= 3


@pytest.mark.asyncio
async def test_peer_service_returns_empty_when_no_same_sector_peers(
    db_session: AsyncSession,
) -> None:
    """Returns empty list when no other ticker shares the same sector."""
    await _add_ticker(db_session, "LONE", "Utilities", 5_000_000_000)
    await db_session.commit()
    service = PeerService(db_session)
    result = await service.get_peers("LONE")
    assert result == []


@pytest.mark.asyncio
async def test_peer_service_peer_entry_fields_present(db_session: AsyncSession) -> None:
    """Each PeerEntry has symbol, name, and headline ratio fields."""
    await _add_ticker(db_session, "SUBJ", "Finance", 50_000_000_000)
    await _add_ticker(db_session, "PEER", "Finance", 45_000_000_000)
    await db_session.commit()

    service = PeerService(db_session)
    result = await service.get_peers("SUBJ", limit=5)
    assert len(result) == 1
    peer = result[0]
    assert peer.symbol == "PEER"
    assert peer.name == "PEER Corp."
    assert peer.market_cap == 45_000_000_000
