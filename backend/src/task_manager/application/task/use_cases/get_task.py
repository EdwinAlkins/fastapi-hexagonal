"""Use case : récupérer une tâche par son identifiant."""

from __future__ import annotations

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId


class GetTask:
    """Récupère une tâche unique."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str) -> TaskDTO:
        task = await self._repository.get(TaskId.from_string(task_id))
        return TaskDTO.from_entity(task)
