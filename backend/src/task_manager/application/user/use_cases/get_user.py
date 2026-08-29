"""Use case : récupérer un utilisateur par son identifiant."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

from task_manager.application.shared.cache import CachePort
from task_manager.application.user.dto import UserDTO
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import UserId

logger = logging.getLogger(__name__)


class GetUser:
    """Récupère un utilisateur unique, en passant par le cache.

    Contrat cache-aside : la clé est ``user:{id}``. Toute mutation d'un ``User``
    doit invalider cette entrée via ``cache.delete(f"user:{id}")`` — c'est ce que
    fait ``RenameUser``. Le port ``CachePort`` expose déjà ``delete`` : pas besoin
    d'un ``invalidate`` dédié.
    """

    def __init__(self, repository: UserRepository, cache: CachePort) -> None:
        self._repository = repository
        self._cache = cache

    async def execute(self, user_id: str) -> UserDTO:
        # L'identifiant est validé avant de toucher au cache : pas d'entrée
        # (ni de lecture) pour un ID syntaxiquement invalide.
        identity = UserId.from_string(user_id)
        key = f"user:{identity}"

        cached = await self._cache.get(key)
        if cached is not None:
            logger.debug("cache hit key=%s", key)
            return self._from_cache(cached)

        logger.debug("cache miss key=%s", key)
        user = await self._repository.get(identity)
        dto = UserDTO.from_entity(user)
        # ``asdict`` et non ``__dict__`` : UserDTO est un dataclass ``slots=True``
        # et n'a donc pas de ``__dict__``.
        await self._cache.set(key, asdict(dto))
        return dto

    @staticmethod
    def _from_cache(payload: dict[str, Any]) -> UserDTO:
        """Reconstruit le DTO depuis le cache : JSON ne connaît pas ``datetime``."""
        return UserDTO(
            id=str(payload["id"]),
            name=str(payload["name"]),
            email=str(payload["email"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )
