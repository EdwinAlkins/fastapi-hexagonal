"""Use case : créer une tâche rattachée à un utilisateur."""

from __future__ import annotations

from task_manager.application.task.dto import CreateTaskCommand, TaskDTO
from task_manager.domain.task.entities import Task
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskTitle
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import UserId


class CreateTask:
    """Orchestre la création d'une tâche.

    Cas typique d'orchestration inter-agrégats dans la couche application : on
    valide l'existence du propriétaire (via le port ``UserRepository``) *avant*
    de créer la tâche. La cohérence référentielle est ainsi vérifiée côté métier,
    en plus de la clé étrangère posée par l'infrastructure.
    """

    def __init__(self, tasks: TaskRepository, users: UserRepository) -> None:
        self._tasks = tasks
        self._users = users

    async def execute(self, command: CreateTaskCommand) -> TaskDTO:
        owner_id = UserId.from_string(command.owner_id)
        if not await self._users.exists(owner_id):
            raise UserNotFound(str(owner_id))

        task = Task.create(
            owner_id=owner_id,
            title=TaskTitle(command.title),
            description=command.description,
        )
        await self._tasks.save(task)
        return TaskDTO.from_entity(task)
