"""
Description: Rule-based support/resistance level detection for the technical
             analysis module. Detects pivot highs/lows in a price series, then
             clusters nearby pivots into distinct levels using an ATR-scaled band.
             Returns ranked SupportResistanceLevel objects with a touch-count
             strength score, so the UI can draw the most significant levels.

             Algorithm:
               1. Pivot detection: a bar is a pivot high (low) if its high (low)
                  is the local extreme over PIVOT_WINDOW bars on each side.
               2. ATR-scaled clustering: pivots whose prices fall within
                  CLUSTER_BAND_ATR_MULT × ATR of each other are merged into one
                  level whose representative price is the mean of the cluster.
               3. Classification: levels above the current close are resistance;
                  levels below (or equal) are support.
               4. Ranking: levels are sorted by strength (touch count) descending.

             All thresholds are named, documented constants.

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; pivot detection + ATR-scaled clustering (Sprint 4-A4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd

from app.services.technical.indicators import IndicatorResult, atr
from app.services.technical.timeframe import PriceBarLike

# ── Constants ──────────────────────────────────────────────────────────────────

# Minimum bars on each side of a pivot bar for it to qualify as a local extreme.
PIVOT_WINDOW: int = 5

# A pivot is merged into an existing cluster when it falls within this many
# ATR multiples of the cluster's representative price.
# ATR-scaled so the band self-adjusts to each ticker's volatility.
CLUSTER_BAND_ATR_MULT: float = 0.5

# Minimum number of bars required to detect any levels at all
# (covers the ATR lookback + at least one pivot window on each side).
MIN_BARS_FOR_LEVELS: int = PIVOT_WINDOW * 2 + 15  # ATR needs 15

# Default maximum number of levels to return (caller can override).
DEFAULT_MAX_LEVELS: int = 10

LevelKind = Literal["support", "resistance"]


# ── Result type ────────────────────────────────────────────────────────────────


@dataclass
class SupportResistanceLevel:
    """A detected price level with strength and metadata.

    Attributes:
        price: Representative price of the level (mean of merged pivots).
        kind: "support" (below current close) or "resistance" (above current close).
        strength: Number of pivots merged into this level (higher = stronger).
        last_touch: Timestamp of the most recent pivot that formed this level.
    """

    price: float
    kind: LevelKind
    strength: int
    last_touch: datetime


# ── Public API ─────────────────────────────────────────────────────────────────


def detect_levels(
    bars: Sequence[PriceBarLike],
    max_levels: int = DEFAULT_MAX_LEVELS,
) -> list[SupportResistanceLevel]:
    """Detect support and resistance levels from a price series.

    Args:
        bars: Price bars (any order; oldest→newest after internal sort).
              Returns empty list when len(bars) < MIN_BARS_FOR_LEVELS.
        max_levels: Maximum number of levels to return, ranked by strength.
                    Defaults to DEFAULT_MAX_LEVELS.

    Returns:
        List of SupportResistanceLevel objects sorted by strength descending.
        Returns an empty list if bars is too short for reliable detection.
    """
    if len(bars) < MIN_BARS_FOR_LEVELS:
        return []

    sorted_bars = sorted(bars, key=lambda b: b.timestamp)
    df = _bars_to_frame(sorted_bars)

    atr_value = _compute_atr(df)
    # ATR may be None (very short series); fall back to a percentage-of-price band.
    band = atr_value * CLUSTER_BAND_ATR_MULT if atr_value else df["close"].iloc[-1] * 0.005

    pivots = _find_pivots(df)
    if not pivots:
        return []

    clusters = _cluster_pivots(pivots, band)
    current_close = float(df["close"].iloc[-1])

    levels = [
        SupportResistanceLevel(
            price=price,
            kind="support" if price <= current_close else "resistance",
            strength=strength,
            last_touch=last_touch,
        )
        for price, strength, last_touch in clusters
    ]

    # Sort by strength descending, cap at max_levels.
    levels.sort(key=lambda lv: lv.strength, reverse=True)
    return levels[:max_levels]


# ── Internal helpers ───────────────────────────────────────────────────────────


def _bars_to_frame(bars: Sequence[PriceBarLike]) -> pd.DataFrame:
    rows = [
        {
            "timestamp": b.timestamp,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume),
        }
        for b in bars
    ]
    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


def _compute_atr(df: pd.DataFrame) -> float | None:
    """Compute the latest ATR from the DataFrame's high/low/close columns."""
    result: IndicatorResult = atr(df["high"], df["low"], df["close"])
    return result.value


@dataclass
class _Pivot:
    """Internal pivot record before clustering."""

    price: float
    timestamp: datetime
    kind: Literal["high", "low"]


def _find_pivots(df: pd.DataFrame, window: int = PIVOT_WINDOW) -> list[_Pivot]:
    """Find local pivot highs and lows in the price series.

    A bar is a pivot high (low) if its high (low) is the maximum (minimum)
    over [i - window, i + window] bars, strictly exceeding all neighbors.
    """
    pivots: list[_Pivot] = []
    highs = df["high"].values
    lows = df["low"].values
    timestamps = df.index.to_list()
    n = len(df)

    for i in range(window, n - window):
        window_highs = highs[i - window : i + window + 1]
        window_lows = lows[i - window : i + window + 1]
        center_high = highs[i]
        center_low = lows[i]

        if center_high == window_highs.max() and (window_highs == center_high).sum() == 1:
            pivots.append(_Pivot(price=float(center_high), timestamp=timestamps[i], kind="high"))

        if center_low == window_lows.min() and (window_lows == center_low).sum() == 1:
            pivots.append(_Pivot(price=float(center_low), timestamp=timestamps[i], kind="low"))

    return pivots


def _cluster_pivots(
    pivots: list[_Pivot],
    band: float,
) -> list[tuple[float, int, datetime]]:
    """Merge nearby pivots into clusters using a fixed price band.

    Args:
        pivots: All detected pivots.
        band: Price tolerance for merging two pivots into the same cluster.

    Returns:
        List of (representative_price, strength, last_touch) tuples.
    """
    if not pivots:
        return []

    # Sort pivots by price to make the greedy grouping stable.
    sorted_pivots = sorted(pivots, key=lambda p: p.price)

    clusters: list[list[_Pivot]] = []
    for pivot in sorted_pivots:
        # Try to merge into the nearest existing cluster within band distance.
        merged = False
        for cluster in clusters:
            rep_price = sum(p.price for p in cluster) / len(cluster)
            if abs(pivot.price - rep_price) <= band:
                cluster.append(pivot)
                merged = True
                break
        if not merged:
            clusters.append([pivot])

    result: list[tuple[float, int, datetime]] = []
    for cluster in clusters:
        rep_price = sum(p.price for p in cluster) / len(cluster)
        last_touch = max(p.timestamp for p in cluster)
        result.append((rep_price, len(cluster), last_touch))

    return result
