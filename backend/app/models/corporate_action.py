"""
Description: SQLAlchemy ORM model for the `corporate_actions` table.
             Stores stock splits and cash dividends for each tracked ticker.
             One row per (ticker_id, action_type, ex_date) — enforced by unique
             constraint to make upsert idempotent.
             `ratio` holds the split ratio (e.g. 2.0 for a 2-for-1 split) or
             the dividend amount per share in the ticker's native currency.
             The split-adjustment worker uses this table to recompute
             `price_bars.adjusted_close` for rows prior to the ex_date.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; CorporateAction model with FK to tickers and
                 unique constraint on (ticker_id, action_type, ex_date).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticker import Ticker

ACTION_TYPE_SPLIT = "split"
ACTION_TYPE_DIVIDEND = "dividend"


class CorporateAction(Base):
    """ORM model for a single corporate-action event in the corporate_actions table."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint(
            "ticker_id",
            "action_type",
            "ex_date",
            name="uq_corporate_actions_ticker_type_exdate",
        ),
        CheckConstraint(
            "action_type IN ('split', 'dividend')",
            name="ck_corporate_actions_action_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(10), nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="corporate_actions")

    def __repr__(self) -> str:
        return (
            f"<CorporateAction id={self.id} ticker_id={self.ticker_id}"
            f" type={self.action_type!r} ex_date={self.ex_date}>"
        )
