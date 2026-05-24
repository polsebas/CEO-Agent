"""Semantic execution cache backed by Redis or in-memory fallback."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.config import settings

_memory_cache: dict[str, tuple[str, float]] = {}
_redis_client = None
_redis_available: bool | None = None


async def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis_client = client
        _redis_available = True
        return _redis_client
    except Exception:
        _redis_client = None
        _redis_available = False
        return None


def _cache_key(tool_name: str, params: dict) -> str:
    payload = json.dumps({"tool": tool_name, "params": params}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


async def cache_get(tool_name: str, params: dict) -> dict | None:
    key = _cache_key(tool_name, params)
    redis = await _get_redis()
    if redis:
        try:
            raw = await redis.get(f"toolcache:{key}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    entry = _memory_cache.get(key)
    return json.loads(entry[0]) if entry else None


async def cache_set(tool_name: str, params: dict, data: dict, ttl: int = 300) -> None:
    key = _cache_key(tool_name, params)
    payload = json.dumps(data)
    redis = await _get_redis()
    if redis:
        try:
            await redis.setex(f"toolcache:{key}", ttl, payload)
            return
        except Exception:
            pass
    import time

    _memory_cache[key] = (payload, time.time() + ttl)


def reset_cache() -> None:
    global _redis_client, _redis_available
    _memory_cache.clear()
    _redis_client = None
    _redis_available = None
