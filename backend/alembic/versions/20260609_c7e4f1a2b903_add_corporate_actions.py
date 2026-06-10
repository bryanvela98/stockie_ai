"""
Description: Add the `corporate_actions` table to track stock splits and
             cash dividends for each tracked ticker.
             Unique constraint on (ticker_id, action_type, ex_date) makes
             upserts idempotent.
             CheckConstraint limits action_type to 'split' or 'dividend'.
             Downgrade drops the table entirely — all corporate-action history
             would be lost, so run the down migration only in development.
Last Modified By: bvela
Created: 2026-06-09
Last Modified:
    2026-06-09 - File created; adds corporate_actions table (Sprint 2-B Task 1).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# ── Alembic metadata ─────────────────────────────────────────────────────────
revision: str = "c7e4f1a2b903"
down_revision: str | Sequence[str] | None = "a1f9c3d2e805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(10), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ticker_id"],
            ["tickers.id"],
            name="fk_corporate_actions_ticker_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker_id",
            "action_type",
            "ex_date",
            name="uq_corporate_actions_ticker_type_exdate",
        ),
        sa.CheckConstraint(
            "action_type IN ('split', 'dividend')",
            name="ck_corporate_actions_action_type",
        ),
    )
    op.create_index(
        "ix_corporate_actions_ticker_id",
        "corporate_actions",
        ["ticker_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_corporate_actions_ticker_id", table_name="corporate_actions")
    op.drop_table("corporate_actions")
