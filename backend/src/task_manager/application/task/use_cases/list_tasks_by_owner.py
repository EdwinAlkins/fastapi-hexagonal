"""Use case : lister les tâches d'un utilisateur (parcours de la relation 1→n)."""

from __future__ import annotations

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import UserId


class ListTasksByOwner:
    """Retourne les tâches appartenant à un utilisateur donné.

    On vérifie d'abord que l'utilisateur existe pour distinguer « user inconnu »
    (404) de « user sans tâche » (liste vide) — deux situations sémantiquement
    différentes du point de vue de l'appelant.
    """

    def __init__(self, tasks: TaskRepository, users: UserRepository) -> None:
        self._tasks = tasks
        self._users = users

    async def execute(self, owner_id: str, *, limit: int = 100, offset: int = 0) -> list[TaskDTO]:
        user_id = UserId.from_string(owner_id)
        if not await self._users.exists(user_id):
            raise UserNotFound(str(user_id))

        tasks = await self._tasks.list_by_owner(user_id, limit=limit, offset=offset)
        return [TaskDTO.from_entity(task) for task in tasks]
