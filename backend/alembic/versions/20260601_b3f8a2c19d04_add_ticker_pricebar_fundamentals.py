"""
Description: Database migration — add tickers, price_bars, and fundamentals tables.
             Creates the three core storage tables for the data provider layer:
               tickers      — master list of tracked equities and ETFs
               price_bars   — OHLCV time-series data (becomes TimescaleDB
                              hypertable in Sprint 2)
               fundamentals — point-in-time fundamental snapshots
             The compound index on price_bars(ticker_id, timestamp) is created
             here to pre-stage the Sprint 2 hypertable conversion.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - Migration created; tickers, price_bars, fundamentals tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "b3f8a2c19d04"
down_revision: str | Sequence[str] | None = "e1663686b91a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── tickers ───────────────────────────────────────────────────────────────
    op.create_table(
        "tickers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=False),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickers_symbol", "tickers", ["symbol"], unique=True)

    # ── price_bars ────────────────────────────────────────────────────────────
    op.create_table(
        "price_bars",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker_id", "timestamp", "interval", name="uq_price_bar_ticker_ts_interval"
        ),
    )
    op.create_index("ix_price_bars_ticker_id_timestamp", "price_bars", ["ticker_id", "timestamp"])

    # ── fundamentals ──────────────────────────────────────────────────────────
    op.create_table(
        "fundamentals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("ps_ratio", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("eps_ttm", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("revenue_ttm", sa.BigInteger(), nullable=True),
        sa.Column("net_income_ttm", sa.BigInteger(), nullable=True),
        sa.Column("roe", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("beta", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("week_52_high", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("week_52_low", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_id", "as_of", name="uq_fundamentals_ticker_as_of"),
    )
    op.create_index("ix_fundamentals_ticker_id", "fundamentals", ["ticker_id"])


def downgrade() -> None:
    op.drop_table("fundamentals")
    op.drop_table("price_bars")
    op.drop_table("tickers")
