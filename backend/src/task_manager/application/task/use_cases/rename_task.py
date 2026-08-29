"""Use case : renommer une tâche."""

from __future__ import annotations

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId, TaskTitle


class RenameTask:
    """Renomme une tâche existante (la validation du titre est portée par le VO)."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str, new_title: str) -> TaskDTO:
        task = await self._repository.get(TaskId.from_string(task_id))
        task.rename(TaskTitle(new_title))
        await self._repository.save(task)
        return TaskDTO.from_entity(task)
