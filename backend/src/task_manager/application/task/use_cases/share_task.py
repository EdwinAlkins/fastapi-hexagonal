"""Use case : partage d'une tâche entre utilisateurs."""

from __future__ import annotations

from task_manager.application.shared.messaging import EventPublisherPort
from task_manager.application.task.dto import ShareTaskNotification
from task_manager.domain.task.exceptions import TaskNotFound
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId


class ShareTask:
    def __init__(self, task_repository: TaskRepository, message_adapter: EventPublisherPort):
        self._task_repository = task_repository
        self._message_adapter = message_adapter

    async def execute(self, task_id: str, user_ids: list[str], subject: str, body: str) -> None:
        if not await self._task_repository.exists(TaskId.from_string(task_id)):
            raise TaskNotFound(f"La tâche {task_id} n'existe pas")
        event = ShareTaskNotification(
            task_id=task_id,
            user_ids=user_ids,
            subject=subject,
            body=body,
        )
        # La clé de routage n'apparaît pas ici : elle est portée par l'événement
        # (``ShareTaskNotification.name``) et traduite par l'adaptateur.
        await self._message_adapter.publish(event)
