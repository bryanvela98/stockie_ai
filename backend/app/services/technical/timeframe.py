"""
Description: Multi-timeframe resampler for the technical analysis module.
             Converts a list of daily PriceBar rows into weekly or monthly OHLCV bars
             in memory — no DB or network access. The price_bars table stores only
             1d bars; weekly and monthly bars are derived on read via this module and
             cached upstream (TechnicalService, Sprint 4-B).

             Resampling rules:
               "1d"  — pass-through (input unchanged).
               "1w"  — week-ending Friday (pandas freq "W-FRI"):
                         open=first, high=max, low=min, close=last,
                         volume=sum, adjusted_close=last (or None if all None).
               "1mo" — calendar month-end (pandas freq "ME"):
                         same OHLCV aggregation rules.

             Partial periods: the incomplete current week/month is included in the
             output and flagged with `is_partial=True` so the UI can mark it.

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; daily→weekly/monthly resampler with partial-period flag (Sprint 4-A3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

import pandas as pd

# ── Structural protocol ────────────────────────────────────────────────────────


class PriceBarLike(Protocol):
    """Structural interface required by the resampler.

    Any object with these attributes satisfies this protocol —
    the ORM PriceBar, the Pydantic DTO, or a lightweight test stub.
    """

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None


# ── Timeframe type ─────────────────────────────────────────────────────────────

Timeframe = Literal["1d", "1w", "1mo"]

VALID_TIMEFRAMES: tuple[str, ...] = ("1d", "1w", "1mo")

# Mapping from our Timeframe strings to pandas resample frequency aliases.
_PANDAS_FREQ: dict[str, str] = {
    "1w": "W-FRI",  # week ending Friday — standard trading convention
    "1mo": "ME",  # month end
}


# ── Result type ────────────────────────────────────────────────────────────────


@dataclass
class ResampledBar:
    """A single OHLCV bar after resampling.

    Attributes:
        timestamp: Period-end timestamp (Friday for weekly; month-end for monthly).
        open: First open in the period.
        high: Maximum high in the period.
        low: Minimum low in the period.
        close: Last close in the period.
        volume: Sum of volume in the period.
        adjusted_close: Last adjusted close, or None if all bars lacked it.
        is_partial: True when this bar represents an incomplete (still-open) period.
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: float | None
    is_partial: bool


# ── Public API ─────────────────────────────────────────────────────────────────


def resample(bars: Sequence[PriceBarLike], timeframe: Timeframe) -> list[ResampledBar]:
    """Aggregate daily OHLCV bars into the requested timeframe.

    Args:
        bars: Daily bars conforming to PriceBarLike (any order; must all be interval="1d").
        timeframe: Target timeframe. "1d" is a pass-through; "1w" and "1mo" aggregate.

    Returns:
        List of ResampledBar objects sorted oldest→newest.
        For "1d", wraps each input bar as a ResampledBar (is_partial=False for all).
        For "1w"/"1mo", each entry spans one period; the last entry has is_partial=True
        if the period is still open (i.e. today falls inside it).

    Raises:
        ValueError: If timeframe is not one of "1d", "1w", "1mo".
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise ValueError(f"Invalid timeframe {timeframe!r}. Must be one of {VALID_TIMEFRAMES}.")

    if not bars:
        return []

    if timeframe == "1d":
        return _passthrough(bars)

    return _resample_ohlcv(bars, timeframe)


# ── Internal helpers ───────────────────────────────────────────────────────────


def _passthrough(bars: Sequence[PriceBarLike]) -> list[ResampledBar]:
    """Wrap daily bars as ResampledBar objects, sorted oldest→newest."""
    sorted_bars = sorted(bars, key=lambda b: b.timestamp)
    return [
        ResampledBar(
            timestamp=b.timestamp,
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=int(b.volume),
            adjusted_close=float(b.adjusted_close) if b.adjusted_close is not None else None,
            is_partial=False,
        )
        for b in sorted_bars
    ]


def _resample_ohlcv(bars: Sequence[PriceBarLike], timeframe: Timeframe) -> list[ResampledBar]:
    """Aggregate daily bars to weekly or monthly OHLCV via pandas resample."""
    freq = _PANDAS_FREQ[timeframe]

    # Build a DataFrame indexed by timestamp (tz-naive for resample compatibility).
    rows = [
        {
            "timestamp": b.timestamp.replace(tzinfo=None) if b.timestamp.tzinfo else b.timestamp,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume),
            "adjusted_close": float(b.adjusted_close) if b.adjusted_close is not None else None,
        }
        for b in bars
    ]
    df = pd.DataFrame(rows).sort_values("timestamp")
    df.set_index("timestamp", inplace=True)

    # Resample with standard OHLCV aggregation.
    agg = df.resample(freq).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        adjusted_close=("adjusted_close", "last"),
    )
    # Drop periods with no data (can appear at the start of the date range).
    agg = agg.dropna(subset=["open", "close"])

    if agg.empty:
        return []

    # Determine which period is the last (potentially incomplete).
    last_idx = agg.index[-1]
    latest_daily = df.index.max()

    result: list[ResampledBar] = []
    for period_end, row in agg.iterrows():
        # A period is partial when the latest available daily bar falls before the
        # period-end anchor (i.e. we haven't reached period close yet).
        is_partial = bool(period_end == last_idx and latest_daily < period_end)
        result.append(
            ResampledBar(
                timestamp=period_end.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                adjusted_close=(
                    float(row["adjusted_close"]) if pd.notna(row["adjusted_close"]) else None
                ),
                is_partial=is_partial,
            )
        )

    return result
