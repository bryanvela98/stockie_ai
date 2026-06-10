"""
Description: Shared pytest fixtures for all test modules.
             Provides a synchronous TestClient (for simple endpoint tests),
             an async HTTPX client, and in-memory SQLite engine/session fixtures
             for repository and worker tests.
             Import these by adding the fixture name as a function parameter —
             pytest resolves them automatically.
Last Modified By: bvela
Created: 2026-05-23
Last Modified:
    2026-05-23 - File created; added sync client and async_client fixtures.
    2026-06-05 - Replaced httpx with httpx2 to silence StarletteDeprecationWarning.
    2026-06-09 - Promoted async_engine and db_session to top-level so workers
                 tests can use the SQLite in-memory fixtures (Sprint 2-B Task 9).
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models as _models  # noqa: F401 — registers all ORM models on Base.metadata
from app.main import app
from app.models.base import Base


@pytest_asyncio.fixture
async def async_engine() -> AsyncIterator[AsyncEngine]:
    """In-memory async SQLite engine with all ORM tables created.

    Available to any test across the test tree; the repositories/conftest.py
    also defines this fixture for backwards compatibility — pytest will prefer
    the nearer scope, so repository tests continue to work unchanged.

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

    Available to any test across the test tree.

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


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Synchronous TestClient for the FastAPI app.

    Scoped to the module so the app is only started once per test file.
    Use this for straightforward, non-async endpoint tests.

    Returns:
        A configured TestClient instance.
    """
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Async HTTPX client for tests that need async semantics.

    Use this when testing endpoints that return streaming responses,
    or when the test itself is async and needs await-able HTTP calls.

    Yields:
        An AsyncClient pointed at the in-process ASGI app.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
