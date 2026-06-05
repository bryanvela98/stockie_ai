"""
Description: Shared pytest fixtures for all test modules.
             Provides a synchronous TestClient (for simple endpoint tests)
             and an async HTTPX client (for tests that need async semantics).
             Import these by adding the fixture name as a function parameter —
             pytest resolves them automatically.
Last Modified By: bvela
Created: 2026-05-23
Last Modified:
    2026-05-23 - File created; added sync client and async_client fixtures.
    2026-06-05 - Replaced httpx with httpx2 to silence StarletteDeprecationWarning.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient

from app.main import app


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
