"""Use case : supprimer une tâche."""

from __future__ import annotations

from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId


class DeleteTask:
    """Supprime une tâche existante."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str) -> None:
        await self._repository.delete(TaskId.from_string(task_id))
