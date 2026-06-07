"""
Description: SQLAlchemy ORM model for the `price_bars` table.
             Stores OHLCV candlestick data for each tracked ticker.
             Primary key is the natural composite (ticker_id, timestamp, interval)
             which satisfies TimescaleDB's requirement that the time-partitioning
             column (timestamp) be present in every unique index including the PK.
             Using the natural key eliminates the surrogate `id` column, reduces
             row size, and avoids SQLite AUTOINCREMENT incompatibility in tests.
             The Sprint 2 Alembic migration converts this table to a hypertable
             partitioned on `timestamp`.
             Upsert-based ingestion is idempotent because the PK uniquely
             identifies each (ticker, point-in-time, granularity) tuple.
             Import alias: files that also import the Pydantic DTO from
             app.data_providers.models should use
             `from app.models.price_bar import PriceBar as PriceBarModel`.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; PriceBar model with FK to tickers, unique
                 constraint, and compound index.
    2026-06-07 - Replaced surrogate id PK with natural composite PK
                 (ticker_id, timestamp, interval) for TimescaleDB hypertable
                 compatibility. Removed UniqueConstraint (now the PK).
                 (Sprint 2-A Task 4).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticker import Ticker


class PriceBar(Base):
    """ORM model for a single OHLCV candlestick row in the price_bars table."""

    __tablename__ = "price_bars"
    __table_args__ = (
        # Compound index for fast time-range queries per ticker.
        # Also satisfies TimescaleDB's requirement that the hypertable PK
        # include the time-partitioning column.
        Index("ix_price_bars_ticker_id_timestamp", "ticker_id", "timestamp"),
    )

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    interval: Mapped[str] = mapped_column(String(10), nullable=False, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="price_bars")

    def __repr__(self) -> str:
        return (
            f"<PriceBar ticker_id={self.ticker_id}"
            f" ts={self.timestamp} interval={self.interval!r}>"
        )
