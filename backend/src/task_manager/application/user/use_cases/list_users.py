"""Use case : lister les utilisateurs."""

from __future__ import annotations

from task_manager.application.user.dto import UserDTO
from task_manager.domain.user.repository import UserRepository


class ListUsers:
    """Retourne l'ensemble des utilisateurs (paginé)."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def execute(self, *, limit: int = 100, offset: int = 0) -> list[UserDTO]:
        users = await self._repository.list(limit=limit, offset=offset)
        return [UserDTO.from_entity(user) for user in users]
