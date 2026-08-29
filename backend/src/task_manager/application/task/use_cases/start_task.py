"""Use case : démarrer une tâche (passage en cours)."""

from __future__ import annotations

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId


class StartTask:
    """Applique la transition « démarrer » à une tâche et la persiste."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str) -> TaskDTO:
        task = await self._repository.get(TaskId.from_string(task_id))
        task.start()
        await self._repository.save(task)
        return TaskDTO.from_entity(task)
