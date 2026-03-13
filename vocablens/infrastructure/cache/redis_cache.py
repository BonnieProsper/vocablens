import json
from typing import Any, Optional

try:
    from redis import asyncio as aioredis  # type: ignore
except ImportError:  # pragma: no cover
    aioredis = None

from vocablens.config.settings import settings


class CacheBackend:
    async def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError


class LRUCacheBackend(CacheBackend):
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self.store: dict[str, Any] = {}
        self.order: list[str] = []

    async def get(self, key: str) -> Optional[Any]:
        if key in self.store:
            self.order.remove(key)
            self.order.append(key)
            return self.store[key]
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:  # ttl ignored
        if key in self.store:
            self.order.remove(key)
        self.store[key] = value
        self.order.append(key)
        if len(self.order) > self.maxsize:
            oldest = self.order.pop(0)
            self.store.pop(oldest, None)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        if key in self.order:
            self.order.remove(key)


class RedisCacheBackend(CacheBackend):
    def __init__(self, url: str):
        self.url = url
        self.client = aioredis.from_url(url) if aioredis else None

    async def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        raw = await self.client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        if not self.client:
            return
        try:
            await self.client.set(key, json.dumps(value), ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception:
            pass


def get_cache_backend() -> CacheBackend:
    if settings.ENABLE_REDIS_CACHE and aioredis and settings.REDIS_URL:
        return RedisCacheBackend(settings.REDIS_URL)
    return LRUCacheBackend()
