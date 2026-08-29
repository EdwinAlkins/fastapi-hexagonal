"""Adaptateur de cache sur Redis/Valkey (``redis.asyncio``)."""

from __future__ import annotations

import logging
from typing import Any

import orjson
from redis.asyncio import Redis
from redis.exceptions import RedisError

from task_manager.application.shared.cache import CachePort

logger = logging.getLogger(__name__)


class RedisCacheAdapter(CachePort):
    """Implémente le port de cache. Le client Redis est injecté (et partagé)."""

    def __init__(self, redis: Redis, *, default_ttl: int) -> None:
        self._redis = redis
        # TTL résolu par la composition root, jamais à l'import du module :
        # la configuration reste injectée plutôt que figée au chargement.
        self._default_ttl = default_ttl

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._redis.get(key)
        except RedisError:
            # Un cache indisponible doit dégrader la latence, pas la
            # disponibilité : on retombe sur la source de vérité.
            logger.warning("cache indisponible en lecture, key=%s", key, exc_info=True)
            return None
        if raw is None:
            return None
        try:
            value: dict[str, Any] = orjson.loads(raw)
        except orjson.JSONDecodeError:
            # Entrée illisible (format changé, écriture corrompue) : on l'ignore
            # et l'appelant reconstruira depuis la base.
            logger.warning("entrée de cache illisible, key=%s", key)
            return None
        return value

    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        try:
            await self._redis.set(key, orjson.dumps(value), ex=ttl or self._default_ttl)
        except RedisError:
            logger.warning("cache indisponible en écriture, key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except RedisError:
            logger.warning("cache indisponible en suppression, key=%s", key, exc_info=True)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except RedisError:
            logger.warning("cache indisponible en ping", exc_info=True)
            return False
