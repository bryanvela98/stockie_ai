"""
Description: SQLAlchemy ORM model for the `fundamentals` table.
             Stores point-in-time fundamental snapshots for each tracked ticker.
             One row per (ticker_id, as_of) date — enforced by unique constraint.
             Populated by YFinanceProvider.get_fundamentals() through
             FundamentalsRepository (Sprint 3).
             All financial metric columns are nullable; coverage varies by
             provider and asset type (e.g. ETFs lack earnings-based ratios).
             Note: debtToEquity from yfinance is a percentage (e.g. 150 = 150%).
             Normalisation to a standard ratio is done in the scoring layer.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; Fundamentals model with FK to tickers and
                 unique constraint on (ticker_id, as_of).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticker import Ticker


class Fundamentals(Base):
    """ORM model for a single fundamental snapshot in the fundamentals table."""

    __tablename__ = "fundamentals"
    __table_args__ = (UniqueConstraint("ticker_id", "as_of", name="uq_fundamentals_ticker_as_of"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    # Valuation
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ps_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Earnings & revenue
    eps_ttm: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    revenue_ttm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_income_ttm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Quality metrics
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Market context
    beta: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    week_52_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    week_52_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="fundamentals")

    def __repr__(self) -> str:
        return f"<Fundamentals id={self.id} ticker_id={self.ticker_id} as_of={self.as_of}>"
