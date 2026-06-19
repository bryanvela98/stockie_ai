"""
Description: Deterministic synthetic price series generators for technical analysis
             golden tests. All generators are pure and seeded — same call always
             produces the same output. Each generator returns a list of stub bars
             that conform to the PriceBarLike protocol.

             Shapes:
               uptrend    — steady day-over-day gains (0.08%/bar); close well above
                            all SMAs by bar 250.
               downtrend  — steady day-over-day losses (0.08%/bar); close below all
                            SMAs by bar 250.
               range_bound — sinusoidal oscillation ±5 around 100; no net direction.
               v_reversal — sharp drop for first half, sharp recovery for second half;
                            the recovery end is near the starting price.
               breakout   — range-bound for first 3/4, then an upside breakout for
                            the final 1/4; close ends well above the range top.

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; deterministic synthetic series for Sprint 4-A6 golden tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal


@dataclass
class SyntheticBar:
    """Minimal price bar stub conforming to PriceBarLike."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None = None
    interval: str = "1d"


def _make_bars(
    closes: list[float],
    spread: float = 0.005,
    start: datetime | None = None,
) -> list[SyntheticBar]:
    """Build SyntheticBar list from close prices.

    Args:
        closes: Ordered list of close prices.
        spread: High/low spread as a fraction of close (default 0.5%).
        start: First bar timestamp. Defaults to (today - n + 1) days ago so
               that the last bar lands on today — keeping all bars inside any
               reasonable lookback window (e.g. BARS_LOOKBACK_DAYS = 550).

    Returns:
        List of SyntheticBar objects, one per close value.
    """
    n = len(closes)
    default_start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=n - 1)
    base = start or default_start
    bars = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        h = c * (1.0 + spread)
        lo = c * (1.0 - spread)
        bars.append(
            SyntheticBar(
                timestamp=base + timedelta(days=i),
                open=Decimal(f"{o:.6f}"),
                high=Decimal(f"{h:.6f}"),
                low=Decimal(f"{lo:.6f}"),
                close=Decimal(f"{c:.6f}"),
                volume=10_000,
            )
        )
    return bars


def uptrend_series(n: int = 250) -> list[SyntheticBar]:
    """Steady uptrend: 0.5% daily gain from a starting price of 100.

    After 250 bars: close ≈ 349. The close will be far above SMA200 (~156),
    SMA50 (~271), and SMA20 (~314), confirming a strong uptrend. Using 0.5%/day
    (vs a gentle 0.08%/day) so that close-vs-SMA trend signals reach well above
    the scoring band caps and the trend subscore exceeds 65.

    Args:
        n: Number of bars (≥ 200 recommended for SMA-200 to populate).
    """
    closes = [100.0 * (1.005**i) for i in range(n)]
    return _make_bars(closes)


def downtrend_series(n: int = 250) -> list[SyntheticBar]:
    """Steady downtrend: 0.5% daily loss from a starting price of 100.

    After 250 bars: close ≈ 29. Close is well below all SMAs.
    Using 0.5%/day so the close-vs-SMA signals breach the scoring band floors
    and the trend subscore falls below 35.

    Args:
        n: Number of bars (≥ 200 recommended).
    """
    closes = [100.0 * (0.995**i) for i in range(n)]
    return _make_bars(closes)


def range_bound_series(n: int = 250) -> list[SyntheticBar]:
    """Sideways range: sinusoidal oscillation between ~95 and ~105.

    Cycle length is 30 bars. No net directional drift. SMAs converge
    toward the mid-range price (~100).

    Args:
        n: Number of bars.
    """
    closes = [100.0 + 5.0 * math.sin(2 * math.pi * i / 30) for i in range(n)]
    return _make_bars(closes)


def v_reversal_series(n: int = 250) -> list[SyntheticBar]:
    """V-shaped reversal: drop then recovery.

    First half: linear decline from 100 to ~70 (−30).
    Second half: linear recovery from ~70 back to ~100.

    The recovery end is at the starting level, making it a clean V.
    RSI will be very low at the bottom (oversold), then recover.

    Args:
        n: Number of bars (must be even).
    """
    half = n // 2
    down = [100.0 - (30.0 * i / half) for i in range(half)]
    up = [70.0 + (30.0 * i / half) for i in range(half)]
    return _make_bars(down + up)


def breakout_series(n: int = 250) -> list[SyntheticBar]:
    """Range-bound then upside breakout.

    First 75%: sinusoidal range between ~97 and ~103 (12-bar micro-cycle).
    Final 25%: linear breakout from the range top to ~125.

    The 12-bar cycle produces clear single-bar pivot highs (at cycle peak i=3,
    15, 27, …) that the pivot detector (PIVOT_WINDOW=5) can identify. A 6-bar
    cycle was avoided because it creates flat double-peaks (two equal adjacent
    bars) that defeat strict-maximum detection.

    Args:
        n: Number of bars.
    """
    range_n = (n * 3) // 4
    breakout_n = n - range_n

    range_prices = [100.0 + 3.0 * math.sin(2 * math.pi * i / 12) for i in range(range_n)]
    # Start breakout from the range top, gain ~0.35% per bar
    start_price = range_prices[-1]
    breakout_prices = [start_price + (22.0 * i / breakout_n) for i in range(breakout_n)]

    return _make_bars(range_prices + breakout_prices)
