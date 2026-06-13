"""
Description: SQLAlchemy ORM model for the `financial_statements` table.
             Stores annual (and future quarterly) financial statement line items
             for each tracked ticker — one row per (ticker_id, fiscal_year, period_type).
             Populated by YFinanceProvider.get_annual_financials() through
             FinancialStatementRepository (Sprint 3-A).
             All financial-amount columns are nullable; coverage varies by asset
             type (ETFs often lack income-statement data). Currency-amount columns
             use BigInteger (whole units); per-share and ratio columns use
             Numeric(18, 6) for precision without float drift.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; FinancialStatement model with FK to tickers and
                 unique constraint on (ticker_id, fiscal_year, period_type).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticker import Ticker

PERIOD_TYPE_ANNUAL = "annual"


class FinancialStatement(Base):
    """ORM model for a single annual (or quarterly) financial-statement snapshot."""

    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint(
            "ticker_id",
            "fiscal_year",
            "period_type",
            name="uq_financial_statements_ticker_year_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False, default=PERIOD_TYPE_ANNUAL)

    # Income statement
    total_revenue: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gross_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operating_income: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # EBIT
    net_income: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    interest_expense: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    eps_diluted: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    # Balance sheet
    total_assets: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_equity: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_debt: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cash_and_equivalents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Cash flow
    operating_cash_flow: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    capital_expenditure: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Share count (diluted, whole shares)
    shares_diluted: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Metadata
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="financial_statements")

    def __repr__(self) -> str:
        return (
            f"<FinancialStatement id={self.id} ticker_id={self.ticker_id}"
            f" fiscal_year={self.fiscal_year} period_type={self.period_type!r}>"
        )
