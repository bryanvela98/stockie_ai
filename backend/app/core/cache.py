"""
Description: Async Redis cache helper for the Stockie AI backend.
             Exposes `get_json` and `set_json` backed by `redis.asyncio`.
             When `redis_url` is None or the Redis server is unreachable,
             every method silently degrades to a no-op (returns None / does
             nothing) so that cache unavailability never fails a request.

             Design intent:
               - Singleton client created lazily on first call; avoids import-time
                 connection attempts.
               - The caller never needs to handle Redis errors — all exceptions are
                 caught and logged at DEBUG level.
               - TTL is always required for set_json; no indefinite-cache keys
                 should exist (prevents stale-score accumulation after restarts).
Last Modified By: bvela
Created: 2026-06-13
Last Modified:
    2026-06-13 - File created; get_json, set_json, and no-op degradation.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis  # type: ignore[import-untyped]

from app.core.config import get_settings

_log = structlog.get_logger(__name__)

# Lazily initialized; None until first use, then either a Redis client or the
# sentinel _DISABLED to avoid repeated failed-init attempts.
_client: Any = None
_DISABLED = object()


async def _get_client() -> Any:
    """Return a live Redis client, or _DISABLED if unavailable.

    Attempts connection once; any subsequent call after a failed init returns
    _DISABLED immediately without retrying (the sentinel avoids log spam).
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.redis_url:
        _log.debug("cache.disabled", reason="redis_url not set")
        _client = _DISABLED
        return _DISABLED

    try:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
        # Ping to confirm the connection is live.
        await _client.ping()
        _log.debug("cache.connected", url=settings.redis_url)
    except Exception as exc:
        _log.debug("cache.init_failed", error=str(exc))
        _client = _DISABLED

    return _client


async def get_json(key: str) -> dict[str, Any] | None:
    """Fetch a JSON-serialised dict from Redis.

    Args:
        key: Cache key to look up.

    Returns:
        Deserialised dict if the key exists and the value is valid JSON,
        otherwise None.
    """
    client = await _get_client()
    if client is _DISABLED:
        return None
    try:
        raw: str | None = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]
    except Exception as exc:
        _log.debug("cache.get_failed", key=key, error=str(exc))
        return None


async def set_json(key: str, value: dict[str, Any], ttl: int) -> None:
    """Serialise a dict to JSON and store it in Redis with an expiry.

    Args:
        key: Cache key to write.
        value: Dict to serialise and store.
        ttl: Expiry in seconds. Must be > 0.
    """
    client = await _get_client()
    if client is _DISABLED:
        return
    try:
        await client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        _log.debug("cache.set_failed", key=key, error=str(exc))
