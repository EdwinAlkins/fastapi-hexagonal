"""Câblage du cache (préoccupation transverse).

Le client Redis est créé une fois au démarrage et rangé dans ``app.state``, comme
le moteur SQLAlchemy : un client construit par requête ouvrirait une connexion à
chaque appel sans jamais la refermer.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from task_manager.application.shared.cache import CachePort
from task_manager.infrastructure.cache.redis_cache import RedisCacheAdapter


def get_cache(request: Request) -> CachePort:
    redis: Redis = request.app.state.redis
    ttl: int = request.app.state.settings.cache_ttl
    return RedisCacheAdapter(redis, default_ttl=ttl)


CachePortDep = Annotated[CachePort, Depends(get_cache)]
