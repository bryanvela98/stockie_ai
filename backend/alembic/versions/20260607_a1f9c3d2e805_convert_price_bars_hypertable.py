"""
Description: Convert price_bars to a TimescaleDB hypertable partitioned on
             `timestamp`. Drops the surrogate `id` column and promotes the
             natural composite key (ticker_id, timestamp, interval) to the
             primary key — satisfying TimescaleDB's requirement that every
             unique index include the partitioning column.
             The downgrade is intentionally left as NotImplementedError:
             converting a hypertable back to a plain table is destructive
             and must be handled manually (dump data, recreate, reload).
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - Migration created; hypertable conversion (Sprint 2-A Task 5).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "a1f9c3d2e805"
down_revision: str | Sequence[str] | None = "b3f8a2c19d04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Drop the old primary key on the surrogate id column.
    op.drop_constraint("price_bars_pkey", "price_bars", type_="primary")

    # Step 2: Drop the unique constraint that will become the new PK.
    # (The old PK was on id; the unique constraint covers the natural key.)
    op.drop_constraint("uq_price_bar_ticker_ts_interval", "price_bars", type_="unique")

    # Step 3: Drop the surrogate id column — it has no meaning in a
    # natural-key schema and wastes storage per row.
    op.drop_column("price_bars", "id")

    # Step 4: Create the composite primary key on the natural key.
    # This is the PK TimescaleDB will use during hypertable conversion.
    op.create_primary_key(
        "pk_price_bars",
        "price_bars",
        ["ticker_id", "timestamp", "interval"],
    )

    # Step 5: Convert to a TimescaleDB hypertable partitioned on timestamp.
    # migrate_data=TRUE is safe on an empty or populated table; it moves
    # existing rows into the first chunk.
    op.execute(
        sa.text(
            "SELECT create_hypertable("
            "  'price_bars',"
            "  'timestamp',"
            "  if_not_exists => TRUE,"
            "  migrate_data => TRUE"
            ")"
        )
    )

    # Step 6: The compound index (ticker_id, timestamp) was created in the
    # previous migration and is preserved through the hypertable conversion.
    # TimescaleDB does not automatically drop user-defined non-PK indexes.


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrading from a TimescaleDB hypertable is not supported automatically. "
        "To revert: stop all ingestion workers, dump the price_bars data, "
        "drop and recreate the table with the old id-based PK, and reload the data."
    )
