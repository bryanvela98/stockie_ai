"""
Description: Shared pytest fixtures for repository-layer tests.
             Provides an in-memory async SQLite engine and an AsyncSession
             bound to it, so repository tests run without a live PostgreSQL
             connection.
             Note: SQLite does not support all PostgreSQL features. Tests here
             verify correctness of CRUD logic; TimescaleDB-specific behaviour
             (hypertables, time_bucket) will be covered by integration tests in
             Sprint 2 that require a running DB.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; async_engine and db_session fixtures.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from app.models.base import Base


@pytest_asyncio.fixture
async def async_engine() -> AsyncIterator[AsyncEngine]:
    """In-memory async SQLite engine with all ORM tables created.

    Yields:
        An AsyncEngine backed by SQLite; all tables from Base.metadata exist.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Async session bound to the in-memory SQLite engine.

    Each test gets a fresh session; the engine (and its data) lives for the
    duration of the test function.

    Yields:
        An AsyncSession with expire_on_commit=False.
    """
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
