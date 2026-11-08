"""Redis cache / rate limiter with an in-memory fallback when Redis is unreachable."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from redis.asyncio import Redis

from app.config import get_settings

log = logging.getLogger("cache")


class Cache:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or get_settings().redis_url
        self._redis: Redis | None = None
        self._mem: dict[str, tuple[float, str]] = {}
        self._redis_ok = True

    def _client(self) -> Redis | None:
        if not self._redis_ok:
            return None
        if self._redis is None:
            self._redis = Redis.from_url(self._url, socket_timeout=1.5, socket_connect_timeout=1.5)
        return self._redis

    def _down(self, exc: Exception) -> None:
        log.warning("redis unavailable, using in-memory cache (%s)", type(exc).__name__)
        self._redis_ok = False

    async def get_json(self, key: str) -> Any | None:
        r = self._client()
        if r is not None:
            try:
                raw = await r.get(key)
                return json.loads(raw) if raw else None
            except Exception as exc:
                self._down(exc)
        item = self._mem.get(key)
        if item and item[0] > time.time():
            return json.loads(item[1])
        return None

    async def set_json(self, key: str, value: Any, ttl_s: int) -> None:
        raw = json.dumps(value, ensure_ascii=False)
        r = self._client()
        if r is not None:
            try:
                await r.set(key, raw, ex=ttl_s)
                return
            except Exception as exc:
                self._down(exc)
        self._mem[key] = (time.time() + ttl_s, raw)

    async def hit(self, key: str, window_s: int = 60) -> int:
        """Increment a fixed-window counter and return its value (rate limiting)."""
        bucket = f"rl:{key}:{int(time.time() // window_s)}"
        r = self._client()
        if r is not None:
            try:
                n = await r.incr(bucket)
                if n == 1:
                    await r.expire(bucket, window_s + 1)
                return int(n)
            except Exception as exc:
                self._down(exc)
        cur = self._mem.get(bucket)
        n = (int(cur[1]) if cur and cur[0] > time.time() else 0) + 1
        self._mem[bucket] = (time.time() + window_s + 1, str(n))
        return n


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


def set_cache(c: Cache | None) -> None:
    global _cache
    _cache = c
