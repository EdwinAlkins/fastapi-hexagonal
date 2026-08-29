"""Use case : lister toutes les tâches."""

from __future__ import annotations

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.repository import TaskRepository


class ListTasks:
    """Retourne l'ensemble des tâches."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, *, limit: int = 100, offset: int = 0) -> list[TaskDTO]:
        tasks = await self._repository.list(limit=limit, offset=offset)
        return [TaskDTO.from_entity(task) for task in tasks]
