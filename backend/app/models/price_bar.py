"""
Description: SQLAlchemy ORM model for the `price_bars` table.
             Stores OHLCV candlestick data for each tracked ticker.
             The unique constraint on (ticker_id, timestamp, interval) makes
             upsert-based ingestion idempotent — re-running the daily ingest
             job will not produce duplicate rows.
             Note: Sprint 2 will convert this table to a TimescaleDB hypertable
             and add the compound index (ticker_id, timestamp) required for
             fast time-range queries. The model definition here pre-stages that
             index so the migration in Sprint 2 is additive only.
             Import alias: files that also import the Pydantic DTO from
             app.data_providers.models should use
             `from app.models.price_bar import PriceBar as PriceBarModel`.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; PriceBar model with FK to tickers, unique
                 constraint, and compound index.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticker import Ticker


class PriceBar(Base):
    """ORM model for a single OHLCV candlestick row in the price_bars table."""

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint(
            "ticker_id",
            "timestamp",
            "interval",
            name="uq_price_bar_ticker_ts_interval",
        ),
        # Pre-staged for Sprint 2 TimescaleDB hypertable conversion
        Index("ix_price_bars_ticker_id_timestamp", "ticker_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="price_bars")

    def __repr__(self) -> str:
        return (
            f"<PriceBar id={self.id} ticker_id={self.ticker_id}"
            f" ts={self.timestamp} interval={self.interval!r}>"
        )
