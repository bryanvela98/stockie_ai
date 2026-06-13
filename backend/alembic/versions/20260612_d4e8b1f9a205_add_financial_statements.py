"""
Description: Add the `financial_statements` table to store annual (and future
             quarterly) financial statement line items for each tracked ticker.
             One row per (ticker_id, fiscal_year, period_type) — enforced by
             unique constraint to make upserts idempotent.
             Downgrade drops the table entirely — all statement history would be
             lost, so run the down migration only in development.
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; adds financial_statements table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# ── Alembic metadata ─────────────────────────────────────────────────────────
revision: str = "d4e8b1f9a205"
down_revision: str | Sequence[str] | None = "c7e4f1a2b903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False, server_default="annual"),
        # Income statement
        sa.Column("total_revenue", sa.BigInteger(), nullable=True),
        sa.Column("gross_profit", sa.BigInteger(), nullable=True),
        sa.Column("operating_income", sa.BigInteger(), nullable=True),
        sa.Column("net_income", sa.BigInteger(), nullable=True),
        sa.Column("interest_expense", sa.BigInteger(), nullable=True),
        sa.Column("eps_diluted", sa.Numeric(18, 6), nullable=True),
        # Balance sheet
        sa.Column("total_assets", sa.BigInteger(), nullable=True),
        sa.Column("total_equity", sa.BigInteger(), nullable=True),
        sa.Column("total_debt", sa.BigInteger(), nullable=True),
        sa.Column("cash_and_equivalents", sa.BigInteger(), nullable=True),
        # Cash flow
        sa.Column("operating_cash_flow", sa.BigInteger(), nullable=True),
        sa.Column("capital_expenditure", sa.BigInteger(), nullable=True),
        # Share count
        sa.Column("shares_diluted", sa.BigInteger(), nullable=True),
        # Metadata
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ticker_id"],
            ["tickers.id"],
            name="fk_financial_statements_ticker_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker_id",
            "fiscal_year",
            "period_type",
            name="uq_financial_statements_ticker_year_period",
        ),
    )
    op.create_index(
        "ix_financial_statements_ticker_id",
        "financial_statements",
        ["ticker_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_statements_ticker_id", table_name="financial_statements")
    op.drop_table("financial_statements")
