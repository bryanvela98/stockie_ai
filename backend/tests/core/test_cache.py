"""
Description: Tests for app.core.cache — the async Redis cache helper.
             All tests run without a live Redis connection by patching the
             module-level _client sentinel. Verifies no-op-mode behaviour
             (None redis_url), get/set round-trip mechanics, JSON
             deserialisation, and graceful degradation on Redis errors.
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; no-op mode and error-degradation tests.
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

import app.core.cache as cache_module
from app.core.cache import get_json, set_json


@pytest.fixture(autouse=True)
def reset_cache_client() -> Generator[None, None, None]:
    """Reset the module-level _client singleton between tests."""
    cache_module._client = None
    yield  # type: ignore[misc]
    cache_module._client = None


# ── no-op mode (redis_url unset) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_json_returns_none_when_redis_url_not_set() -> None:
    """get_json returns None without connecting when redis_url is None."""
    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = None
        result = await get_json("some:key")
    assert result is None


@pytest.mark.asyncio
async def test_set_json_is_noop_when_redis_url_not_set() -> None:
    """set_json completes without raising when redis_url is None."""
    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = None
        await set_json("some:key", {"x": 1}, ttl=60)  # must not raise


# ── error degradation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_json_returns_none_on_connection_error() -> None:
    """get_json degrades to None when Redis ping fails on init."""
    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:9999"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            instance = AsyncMock()
            instance.ping.side_effect = ConnectionRefusedError("refused")
            mock_redis_cls.from_url.return_value = instance
            result = await get_json("k")
    assert result is None


@pytest.mark.asyncio
async def test_set_json_is_noop_on_connection_error() -> None:
    """set_json degrades silently when Redis ping fails on init."""
    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:9999"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            instance = AsyncMock()
            instance.ping.side_effect = ConnectionRefusedError("refused")
            mock_redis_cls.from_url.return_value = instance
            await set_json("k", {"a": 1}, ttl=60)  # must not raise


# ── happy path (mocked live client) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_json_returns_dict_on_cache_hit() -> None:
    """get_json deserialises a JSON string returned by Redis."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.get = AsyncMock(return_value='{"score": 42.0}')

    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis
            result = await get_json("fundamentals:v1.0:AAPL:2024-09-28")

    assert result == {"score": 42.0}


@pytest.mark.asyncio
async def test_get_json_returns_none_on_cache_miss() -> None:
    """get_json returns None when Redis returns None (key absent)."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis
            result = await get_json("missing:key")

    assert result is None


@pytest.mark.asyncio
async def test_set_json_calls_setex_with_correct_args() -> None:
    """set_json calls Redis SETEX with the serialised payload and TTL."""
    import json

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis
            await set_json("k", {"value": 99}, ttl=86400)

    mock_redis.setex.assert_called_once_with("k", 86400, json.dumps({"value": 99}))


@pytest.mark.asyncio
async def test_get_json_degrades_on_redis_error_after_init() -> None:
    """get_json returns None when client.get() raises after successful init."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=OSError("connection lost"))

    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        with patch("app.core.cache.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis
            result = await get_json("k")

    assert result is None
