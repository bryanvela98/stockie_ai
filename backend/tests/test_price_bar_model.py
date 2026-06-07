"""
Description: Unit tests for the PriceBar SQLAlchemy model structure.
             Verifies the composite PK required for TimescaleDB hypertable
             conversion and the pre-staged compound index.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; composite PK and index structure tests.
"""

from app.models.price_bar import PriceBar

_table = PriceBar.__table__  # type: ignore[attr-defined]


def test_price_bar_primary_key_includes_timestamp() -> None:
    """PriceBar PK must include 'timestamp' for TimescaleDB hypertable compatibility."""
    pk_col_names = {col.name for col in PriceBar.__table__.primary_key}  # type: ignore[attr-defined]
    assert "timestamp" in pk_col_names, (
        "TimescaleDB requires the time column to be part of every unique index, "
        "including the primary key."
    )


def test_price_bar_primary_key_is_natural_composite() -> None:
    """PriceBar PK is the natural composite (ticker_id, timestamp, interval).

    Using the natural key as PK:
    - satisfies TimescaleDB's requirement to include the time column in the PK
    - eliminates the surrogate id column (smaller rows, simpler inserts)
    - avoids SQLite AUTOINCREMENT incompatibility in tests
    """
    pk_col_names = {col.name for col in PriceBar.__table__.primary_key}  # type: ignore[attr-defined]
    assert pk_col_names == {"ticker_id", "timestamp", "interval"}


def test_price_bar_no_surrogate_id_column() -> None:
    """PriceBar must not have a surrogate 'id' column (removed in Sprint 2)."""
    col_names = {col.name for col in PriceBar.__table__.c}  # type: ignore[attr-defined]
    assert "id" not in col_names


def test_price_bar_compound_index_exists() -> None:
    """Pre-staged compound index (ticker_id, timestamp) must be defined on the table."""
    index_names = {idx.name for idx in PriceBar.__table__.indexes}  # type: ignore[attr-defined]
    assert "ix_price_bars_ticker_id_timestamp" in index_names
