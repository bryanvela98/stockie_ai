"""
Description: Unit tests for the support/resistance level detector in
             app.services.technical.levels. All tests use in-memory data
             (the _Bar stub and synthetic price series) — no DB or network.
             Covers pivot detection, ATR-scaled clustering, classification,
             ranking, and short-series empty-list guard.
Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; levels detection tests (Sprint 4-A4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.technical.levels import (
    MIN_BARS_FOR_LEVELS,
    SupportResistanceLevel,
    detect_levels,
)

# ── Stub bar ───────────────────────────────────────────────────────────────────


@dataclass
class _Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None = None


def _bar(
    ts: datetime,
    o: float,
    h: float,
    lo: float,
    c: float,
) -> _Bar:
    return _Bar(
        timestamp=ts,
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(lo)),
        close=Decimal(str(c)),
        volume=1000,
    )


def _make_daily_bars(prices: list[float], start: datetime | None = None) -> list[_Bar]:
    """Build _Bar stubs from a list of close prices.

    Open = prev_close (or first close), high = close + 0.1, low = close - 0.1.
    Each bar is one day apart starting from `start`.
    """
    base = start or datetime(2024, 1, 1, tzinfo=UTC)
    bars = []
    for i, c in enumerate(prices):
        o = prices[i - 1] if i > 0 else c
        bars.append(_bar(base + timedelta(days=i), o, c + 0.1, c - 0.1, c))
    return bars


# ── Short-series guard ─────────────────────────────────────────────────────────


def test_too_few_bars_returns_empty() -> None:
    bars = _make_daily_bars([10.0] * (MIN_BARS_FOR_LEVELS - 1))
    result = detect_levels(bars)
    assert result == []


# ── Pivot detection via known double-top ──────────────────────────────────────


def _double_top_series(n_flat: int = 20) -> list[float]:
    """Return a price series with a clear double-top pattern.

    Structure: flat → spike to 110 → return to 100 → spike to 110 → return to 100.
    The two spikes form matching pivot highs that should cluster into one resistance level.
    """
    flat = [100.0] * n_flat
    spike1 = [101, 104, 107, 110, 107, 104, 101, 100]
    flat2 = [100.0] * n_flat
    spike2 = [101, 104, 107, 110, 107, 104, 101, 100]
    flat3 = [100.0] * n_flat
    return flat + spike1 + flat2 + spike2 + flat3


def test_double_top_detects_resistance_level() -> None:
    """The two ~110 spike tops should cluster into a single resistance level."""
    prices = _double_top_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    resistance_levels = [lv for lv in levels if lv.kind == "resistance"]
    # Current close is ~100; the ~110 cluster should be the dominant resistance.
    assert len(resistance_levels) >= 1
    top_resistance = max(resistance_levels, key=lambda lv: lv.price)
    assert 108.0 <= top_resistance.price <= 112.0


def test_double_top_resistance_has_strength_gte_2() -> None:
    """Two nearly identical pivot highs must merge into one level with strength ≥ 2."""
    prices = _double_top_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    resistance_levels = [lv for lv in levels if lv.kind == "resistance"]
    top_resistance = max(resistance_levels, key=lambda lv: lv.price)
    assert top_resistance.strength >= 2


# ── Double-bottom (support) ────────────────────────────────────────────────────


def _double_bottom_series(n_flat: int = 20) -> list[float]:
    flat = [100.0] * n_flat
    dip1 = [99, 96, 93, 90, 93, 96, 99, 100]
    flat2 = [100.0] * n_flat
    dip2 = [99, 96, 93, 90, 93, 96, 99, 100]
    flat3 = [100.0] * n_flat
    return flat + dip1 + flat2 + dip2 + flat3


def test_double_bottom_detects_support_level() -> None:
    """The two ~90 dip bottoms should cluster into a single support level."""
    prices = _double_bottom_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    support_levels = [lv for lv in levels if lv.kind == "support"]
    assert len(support_levels) >= 1
    bottom_support = min(support_levels, key=lambda lv: lv.price)
    assert 88.0 <= bottom_support.price <= 92.0


def test_double_bottom_support_strength_gte_2() -> None:
    prices = _double_bottom_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    support_levels = [lv for lv in levels if lv.kind == "support"]
    bottom_support = min(support_levels, key=lambda lv: lv.price)
    assert bottom_support.strength >= 2


# ── Classification ─────────────────────────────────────────────────────────────


def test_levels_above_close_are_resistance() -> None:
    """Every level with price > current close must be classified as resistance."""
    prices = _double_top_series()
    bars = _make_daily_bars(prices)
    current_close = prices[-1]
    levels = detect_levels(bars)
    for lv in levels:
        if lv.price > current_close:
            assert lv.kind == "resistance", f"Level at {lv.price} should be resistance"


def test_levels_below_close_are_support() -> None:
    """Every level with price ≤ current close must be classified as support."""
    prices = _double_bottom_series()
    bars = _make_daily_bars(prices)
    current_close = prices[-1]
    levels = detect_levels(bars)
    for lv in levels:
        if lv.price <= current_close:
            assert lv.kind == "support", f"Level at {lv.price} should be support"


# ── Ranking and return type ────────────────────────────────────────────────────


def test_levels_sorted_by_strength_descending() -> None:
    prices = _double_top_series() + _double_bottom_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    strengths = [lv.strength for lv in levels]
    assert strengths == sorted(strengths, reverse=True)


def test_max_levels_cap_respected() -> None:
    prices = _double_top_series() + _double_bottom_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars, max_levels=3)
    assert len(levels) <= 3


def test_returns_support_resistance_level_instances() -> None:
    prices = _double_top_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    assert all(isinstance(lv, SupportResistanceLevel) for lv in levels)


def test_strength_positive() -> None:
    prices = _double_top_series()
    bars = _make_daily_bars(prices)
    levels = detect_levels(bars)
    assert all(lv.strength >= 1 for lv in levels)


def test_empty_input_returns_empty() -> None:
    assert detect_levels([]) == []
