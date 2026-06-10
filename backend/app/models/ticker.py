"""
Description: SQLAlchemy ORM model for the `tickers` table.
             Stores static metadata for each tracked equity or ETF — symbol,
             name, exchange, asset type, sector, and industry.
             All OHLCV and fundamentals rows reference this table via FK.
             Populated by YFinanceProvider.get_ticker_info() through
             TickerRepository.upsert().
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; Ticker model with relationships to PriceBar and
                 Fundamentals.
    2026-06-09 - Added corporate_actions relationship (Sprint 2-B Task 1).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.corporate_action import CorporateAction
    from app.models.fundamentals import Fundamentals
    from app.models.price_bar import PriceBar


class Ticker(Base):
    """ORM model representing a single equity or ETF in the tickers master table."""

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships — populated lazily; use selectinload/joinedload at query time
    price_bars: Mapped[list["PriceBar"]] = relationship(
        "PriceBar", back_populates="ticker", cascade="all, delete-orphan"
    )
    fundamentals: Mapped[list["Fundamentals"]] = relationship(
        "Fundamentals", back_populates="ticker", cascade="all, delete-orphan"
    )
    corporate_actions: Mapped[list["CorporateAction"]] = relationship(
        "CorporateAction", back_populates="ticker", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ticker id={self.id} symbol={self.symbol!r} exchange={self.exchange!r}>"
