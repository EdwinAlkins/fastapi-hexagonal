"""Câblage des use cases du bounded context ``task``."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from task_manager.application.task.queries import TaskQueryPort
from task_manager.application.task.use_cases.complete_task import CompleteTask
from task_manager.application.task.use_cases.create_task import CreateTask
from task_manager.application.task.use_cases.delete_task import DeleteTask
from task_manager.application.task.use_cases.get_task import GetTask
from task_manager.application.task.use_cases.list_tasks import ListTasks
from task_manager.application.task.use_cases.list_tasks_by_owner import ListTasksByOwner
from task_manager.application.task.use_cases.rename_task import RenameTask
from task_manager.application.task.use_cases.share_task import ShareTask
from task_manager.application.task.use_cases.start_task import StartTask
from task_manager.infrastructure.persistence.task.queries import SqlAlchemyTaskQueryService
from task_manager.presentation.api.dependencies.messaging import MessageAdapterDep
from task_manager.presentation.api.dependencies.repositories import (
    TaskRepositoryDep,
    UserRepositoryDep,
)
from task_manager.presentation.api.dependencies.session import SessionDep


def get_create_task(tasks: TaskRepositoryDep, users: UserRepositoryDep) -> CreateTask:
    # Use case inter-agrégats : dépend des deux ports.
    return CreateTask(tasks, users)


def get_get_task(tasks: TaskRepositoryDep) -> GetTask:
    return GetTask(tasks)


def get_list_tasks(tasks: TaskRepositoryDep) -> ListTasks:
    return ListTasks(tasks)


def get_list_tasks_by_owner(session: SessionDep, users: UserRepositoryDep) -> ListTasksByOwner:
    return ListTasksByOwner(SqlAlchemyTaskQueryService(session), users)


def get_complete_task(tasks: TaskRepositoryDep) -> CompleteTask:
    return CompleteTask(tasks)


def get_start_task(tasks: TaskRepositoryDep) -> StartTask:
    return StartTask(tasks)


def get_rename_task(tasks: TaskRepositoryDep) -> RenameTask:
    return RenameTask(tasks)


def get_delete_task(tasks: TaskRepositoryDep) -> DeleteTask:
    return DeleteTask(tasks)


def get_share_task(tasks: TaskRepositoryDep, messaging: MessageAdapterDep) -> ShareTask:
    return ShareTask(tasks, messaging)


# ── Chemin de LECTURE ────────────────────────────────────────────────────────
# Pas de use case ici : il n'y aurait rien à orchestrer. Le router appelle le port
# directement — le chemin de lecture a deux niveaux là où l'écriture en a quatre
# (router → use case → domaine → repository).
def get_task_query_service(session: SessionDep) -> TaskQueryPort:
    return SqlAlchemyTaskQueryService(session)


TaskQueryDep = Annotated[TaskQueryPort, Depends(get_task_query_service)]
