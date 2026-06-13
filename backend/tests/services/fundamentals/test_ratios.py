"""
Description: Unit tests for the valuation-ratio calculator functions in
             app.services.fundamentals.ratios. All tests use a minimal
             Fundamentals ORM instance constructed in memory — no DB, no
             network. Covers happy paths and all None-guard branches.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; happy paths and None-guard tests for every ratio.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.fundamentals import Fundamentals
from app.services.fundamentals.ratios import (
    ValuationRatios,
    compute_valuation_ratios,
    dividend_yield,
    ev_ebitda,
    pb,
    pe,
    peg,
    ps,
)

# ── fixture ───────────────────────────────────────────────────────────────────


def _snapshot(**overrides: object) -> Fundamentals:
    """Build a minimal Fundamentals ORM instance without hitting the DB."""
    defaults: dict[str, object] = {
        "id": 1,
        "ticker_id": 1,
        "as_of": date(2024, 9, 28),
        "pe_ratio": Decimal("29.50"),
        "pb_ratio": Decimal("46.20"),
        "ps_ratio": Decimal("8.10"),
        "ev_ebitda": Decimal("23.40"),
        "dividend_yield": Decimal("0.005"),
    }
    defaults.update(overrides)
    return Fundamentals(**defaults)  # type: ignore[arg-type]


# ── pe ────────────────────────────────────────────────────────────────────────


def test_pe_returns_float_from_snapshot() -> None:
    """P/E is extracted from the snapshot's pe_ratio column and cast to float."""
    snap = _snapshot(pe_ratio=Decimal("29.50"))
    assert pe(snap) == pytest.approx(29.50)


def test_pe_returns_none_when_missing() -> None:
    """P/E is None when pe_ratio is not in the snapshot."""
    snap = _snapshot(pe_ratio=None)
    assert pe(snap) is None


# ── pb ────────────────────────────────────────────────────────────────────────


def test_pb_returns_float_from_snapshot() -> None:
    snap = _snapshot(pb_ratio=Decimal("46.20"))
    assert pb(snap) == pytest.approx(46.20)


def test_pb_returns_none_when_missing() -> None:
    snap = _snapshot(pb_ratio=None)
    assert pb(snap) is None


# ── ps ────────────────────────────────────────────────────────────────────────


def test_ps_returns_float_from_snapshot() -> None:
    snap = _snapshot(ps_ratio=Decimal("8.10"))
    assert ps(snap) == pytest.approx(8.10)


def test_ps_returns_none_when_missing() -> None:
    snap = _snapshot(ps_ratio=None)
    assert ps(snap) is None


# ── ev_ebitda ─────────────────────────────────────────────────────────────────


def test_ev_ebitda_returns_float_from_snapshot() -> None:
    snap = _snapshot(ev_ebitda=Decimal("23.40"))
    assert ev_ebitda(snap) == pytest.approx(23.40)


def test_ev_ebitda_returns_none_when_missing() -> None:
    snap = _snapshot(ev_ebitda=None)
    assert ev_ebitda(snap) is None


# ── dividend_yield ────────────────────────────────────────────────────────────


def test_dividend_yield_returns_float_from_snapshot() -> None:
    snap = _snapshot(dividend_yield=Decimal("0.005"))
    assert dividend_yield(snap) == pytest.approx(0.005)


def test_dividend_yield_returns_none_when_missing() -> None:
    snap = _snapshot(dividend_yield=None)
    assert dividend_yield(snap) is None


# ── peg ───────────────────────────────────────────────────────────────────────


def test_peg_computes_correctly() -> None:
    """PEG = P/E / growth_rate_percent. With P/E=30 and 15 % growth → PEG=2.0."""
    assert peg(30.0, 15.0) == pytest.approx(2.0)


def test_peg_returns_none_when_pe_missing() -> None:
    assert peg(None, 15.0) is None


def test_peg_returns_none_when_growth_missing() -> None:
    assert peg(30.0, None) is None


def test_peg_returns_none_when_growth_zero() -> None:
    """Zero growth makes PEG meaningless (division by zero)."""
    assert peg(30.0, 0.0) is None


def test_peg_returns_none_when_growth_negative() -> None:
    """Negative growth produces a negative PEG which has no standard interpretation."""
    assert peg(30.0, -5.0) is None


# ── compute_valuation_ratios ──────────────────────────────────────────────────


def test_compute_valuation_ratios_returns_dataclass() -> None:
    """compute_valuation_ratios returns a ValuationRatios with all fields."""
    snap = _snapshot()
    result = compute_valuation_ratios(snap, eps_growth_rate=15.0)

    assert isinstance(result, ValuationRatios)
    assert result.pe == pytest.approx(29.50)
    assert result.pb == pytest.approx(46.20)
    assert result.ps == pytest.approx(8.10)
    assert result.ev_ebitda == pytest.approx(23.40)
    assert result.dividend_yield == pytest.approx(0.005)
    assert result.peg == pytest.approx(29.50 / 15.0)


def test_compute_valuation_ratios_peg_none_when_no_growth() -> None:
    """peg field is None when eps_growth_rate is not supplied."""
    snap = _snapshot()
    result = compute_valuation_ratios(snap)
    assert result.peg is None


def test_compute_valuation_ratios_all_none_snapshot() -> None:
    """All ratios are None for a snapshot where no metric fields are set."""
    snap = _snapshot(
        pe_ratio=None,
        pb_ratio=None,
        ps_ratio=None,
        ev_ebitda=None,
        dividend_yield=None,
    )
    result = compute_valuation_ratios(snap, eps_growth_rate=10.0)
    assert result.pe is None
    assert result.pb is None
    assert result.ps is None
    assert result.ev_ebitda is None
    assert result.dividend_yield is None
    assert result.peg is None
