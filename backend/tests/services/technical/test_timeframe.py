"""
Description: Unit tests for the multi-timeframe resampler in
             app.services.technical.timeframe. Uses a lightweight stub instead of
             the ORM model to avoid DB setup — all tests are pure in-memory.
             Covers daily pass-through, weekly/monthly aggregation (OHLCV rules),
             partial-period detection, unknown timeframe error, and empty input.
Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; timeframe resampler tests (Sprint 4-A3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.technical.timeframe import ResampledBar, resample

# ── Stub PriceBar ──────────────────────────────────────────────────────────────


@dataclass
class _Bar:
    """Minimal PriceBar stub — same interface as the ORM model, no DB required."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None = None
    interval: str = "1d"


def _bar(
    ts: str,
    o: float,
    h: float,
    lo: float,
    c: float,
    vol: int = 1000,
    adj: float | None = None,
) -> _Bar:
    """Helper to create a _Bar from string date (YYYY-MM-DD) and floats."""
    dt = datetime.strptime(ts, "%Y-%m-%d").replace(tzinfo=UTC)
    return _Bar(
        timestamp=dt,
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(lo)),
        close=Decimal(str(c)),
        volume=vol,
        adjusted_close=Decimal(str(adj)) if adj is not None else None,
    )


# ── Pass-through (1d) ──────────────────────────────────────────────────────────


def test_daily_passthrough_preserves_all_bars() -> None:
    bars = [_bar("2024-01-02", 10, 11, 9, 10.5), _bar("2024-01-03", 10.5, 12, 10, 11)]
    result = resample(bars, "1d")
    assert len(result) == 2


def test_daily_passthrough_sorted_oldest_first() -> None:
    bars = [_bar("2024-01-03", 10.5, 12, 10, 11), _bar("2024-01-02", 10, 11, 9, 10.5)]
    result = resample(bars, "1d")
    assert result[0].timestamp < result[1].timestamp


def test_daily_passthrough_preserves_ohlcv() -> None:
    bars = [_bar("2024-01-02", 10.0, 11.0, 9.0, 10.5, vol=5000, adj=10.4)]
    result = resample(bars, "1d")
    r = result[0]
    assert r.open == pytest.approx(10.0)
    assert r.high == pytest.approx(11.0)
    assert r.low == pytest.approx(9.0)
    assert r.close == pytest.approx(10.5)
    assert r.volume == 5000
    assert r.adjusted_close == pytest.approx(10.4)
    assert r.is_partial is False


def test_daily_passthrough_none_adjusted_close() -> None:
    bars = [_bar("2024-01-02", 10, 11, 9, 10.5)]
    result = resample(bars, "1d")
    assert result[0].adjusted_close is None


# ── Weekly resampling ──────────────────────────────────────────────────────────


def test_weekly_aggregates_one_full_week() -> None:
    """Mon–Fri bars fold into a single weekly bar ending Friday."""
    week = [
        _bar("2024-01-08", 10, 11, 9, 10.5, vol=100),  # Mon
        _bar("2024-01-09", 10.5, 12, 10, 11, vol=200),  # Tue
        _bar("2024-01-10", 11, 13, 10.5, 12, vol=150),  # Wed
        _bar("2024-01-11", 12, 12.5, 11, 11.5, vol=80),  # Thu
        _bar("2024-01-12", 11.5, 12, 11, 11.8, vol=120),  # Fri
    ]
    result = resample(week, "1w")
    assert len(result) == 1
    r = result[0]
    # open=first(10.0), high=max(13.0), low=min(9.0), close=last(11.8), volume=sum(650)
    assert r.open == pytest.approx(10.0)
    assert r.high == pytest.approx(13.0)
    assert r.low == pytest.approx(9.0)
    assert r.close == pytest.approx(11.8)
    assert r.volume == 650


def test_weekly_two_full_weeks() -> None:
    """Two separate Mon–Fri blocks each become one weekly bar."""
    week1_dates = ["2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]
    week2_dates = ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"]
    week1 = [_bar(d, 10.0, 11.0, 9.0, 10.5) for d in week1_dates]
    week2 = [_bar(d, 11.0, 12.0, 10.0, 11.5) for d in week2_dates]
    result = resample(week1 + week2, "1w")
    assert len(result) == 2


def test_weekly_partial_week_is_flagged() -> None:
    """A series ending mid-week should have the last bar marked is_partial=True."""
    bars = [
        _bar("2024-01-08", 10, 11, 9, 10.5),  # Mon
        _bar("2024-01-09", 10.5, 12, 10, 11),  # Tue (series ends mid-week)
    ]
    result = resample(bars, "1w")
    # Last bar is the incomplete week — must be flagged
    assert result[-1].is_partial is True


def test_weekly_complete_week_last_bar_not_partial() -> None:
    """A full Mon–Fri week should NOT be flagged as partial."""
    week = [
        _bar("2024-01-08", 10, 11, 9, 10.5),
        _bar("2024-01-09", 10.5, 12, 10, 11),
        _bar("2024-01-10", 11, 13, 10.5, 12),
        _bar("2024-01-11", 12, 12.5, 11, 11.5),
        _bar("2024-01-12", 11.5, 12, 11, 11.8),  # Fri — period closes exactly here
    ]
    result = resample(week, "1w")
    assert result[-1].is_partial is False


# ── Monthly resampling ─────────────────────────────────────────────────────────


def test_monthly_aggregates_full_month() -> None:
    """All bars in January 2024 fold into one monthly bar."""
    bars = [
        _bar("2024-01-02", 10, 11, 9, 10.5, vol=100),
        _bar("2024-01-15", 10.5, 12, 10, 11, vol=200),
        _bar("2024-01-31", 11, 13, 10.5, 12, vol=150),
    ]
    result = resample(bars, "1mo")
    assert len(result) == 1
    r = result[0]
    assert r.open == pytest.approx(10.0)
    assert r.high == pytest.approx(13.0)
    assert r.low == pytest.approx(9.0)
    assert r.close == pytest.approx(12.0)
    assert r.volume == 450


def test_monthly_two_months_produce_two_bars() -> None:
    jan = [_bar("2024-01-02", 10, 11, 9, 10.5), _bar("2024-01-15", 10.5, 12, 10, 11)]
    feb = [_bar("2024-02-01", 11, 12, 10, 11.5), _bar("2024-02-15", 11.5, 13, 11, 12)]
    result = resample(jan + feb, "1mo")
    assert len(result) == 2


def test_monthly_partial_month_is_flagged() -> None:
    """A month-to-date series ending before month-end should be flagged is_partial."""
    bars = [
        _bar("2024-01-02", 10, 11, 9, 10.5),
        _bar("2024-01-15", 10.5, 12, 10, 11),  # ends mid-month
    ]
    result = resample(bars, "1mo")
    assert result[-1].is_partial is True


def test_monthly_volume_summed() -> None:
    bars = [
        _bar("2024-01-02", 10, 11, 9, 10.5, vol=300),
        _bar("2024-01-15", 10.5, 12, 10, 11, vol=700),
    ]
    result = resample(bars, "1mo")
    assert result[0].volume == 1000


# ── Edge cases ─────────────────────────────────────────────────────────────────


def test_empty_bars_returns_empty() -> None:
    for tf in ("1d", "1w", "1mo"):
        assert resample([], tf) == []  # type: ignore[arg-type]


def test_invalid_timeframe_raises_value_error() -> None:
    bars = [_bar("2024-01-02", 10, 11, 9, 10.5)]
    with pytest.raises(ValueError, match="Invalid timeframe"):
        resample(bars, "2h")  # type: ignore[arg-type]


def test_returns_resampled_bar_instances() -> None:
    bars = [_bar("2024-01-02", 10, 11, 9, 10.5)]
    result = resample(bars, "1mo")
    assert all(isinstance(r, ResampledBar) for r in result)
