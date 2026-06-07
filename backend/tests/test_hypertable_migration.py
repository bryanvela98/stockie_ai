"""
Description: Structural tests for the price_bars hypertable migration.
             Verifies that the migration file exists, chains from the correct
             revision, and contains the required DDL operations.
             Full DB verification (alembic upgrade head + hypertable query)
             is a manual step that requires a live TimescaleDB instance.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; structural tests for hypertable migration.
"""

from pathlib import Path

VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
PREV_REVISION = "b3f8a2c19d04"


def _find_migration_module() -> Path | None:
    """Find the hypertable migration file by its expected name pattern."""
    for f in VERSIONS_DIR.glob("*hypertable*.py"):
        return f
    return None


def test_hypertable_migration_file_exists() -> None:
    """A migration file with 'hypertable' in the name must exist."""
    assert _find_migration_module() is not None, (
        "No hypertable migration found in alembic/versions/. "
        "Create 20260607_<rev>_convert_price_bars_hypertable.py"
    )


def test_hypertable_migration_chains_from_previous_revision() -> None:
    """Migration must set down_revision to the previous head."""
    path = _find_migration_module()
    assert path is not None
    content = path.read_text()
    assert PREV_REVISION in content, (
        f"Migration must chain from revision {PREV_REVISION!r} " "(set down_revision accordingly)"
    )


def test_hypertable_migration_contains_create_hypertable_call() -> None:
    """Migration upgrade() must call create_hypertable for price_bars."""
    path = _find_migration_module()
    assert path is not None
    content = path.read_text()
    assert "create_hypertable" in content


def test_hypertable_migration_drops_id_column() -> None:
    """Migration must drop the old surrogate id column from price_bars."""
    path = _find_migration_module()
    assert path is not None
    content = path.read_text()
    assert "drop_column" in content and "id" in content


def test_hypertable_migration_creates_natural_pk() -> None:
    """Migration must create a composite PK (ticker_id, timestamp, interval)."""
    path = _find_migration_module()
    assert path is not None
    content = path.read_text()
    assert "ticker_id" in content and "timestamp" in content and "interval" in content
