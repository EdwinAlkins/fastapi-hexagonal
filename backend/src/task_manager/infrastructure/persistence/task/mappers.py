"""Conversion entre l'agrégat ``Task`` et son modèle ORM."""

from __future__ import annotations

from task_manager.domain.task.entities import Task
from task_manager.domain.task.value_objects import TaskId, TaskStatus, TaskTitle
from task_manager.domain.user.value_objects import UserId
from task_manager.infrastructure.persistence.converters import as_utc
from task_manager.infrastructure.persistence.task.models import TaskModel


def to_model(task: Task) -> TaskModel:
    """Domaine → ORM (nouvelle ligne)."""
    return TaskModel(
        id=task.id.value,
        owner_id=task.owner_id.value,
        title=str(task.title),
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


def apply_to_model(model: TaskModel, task: Task) -> None:
    """Domaine → ORM (mise à jour en place d'une ligne existante).

    ``id``, ``owner_id`` et ``created_at`` sont immuables : on ne remappe que ce
    qui évolue.
    """
    model.title = str(task.title)
    model.description = task.description
    model.status = task.status.value
    model.completed_at = task.completed_at


def to_domain(model: TaskModel) -> Task:
    """ORM → domaine."""
    return Task.reconstitute(
        id=TaskId(model.id),
        owner_id=UserId(model.owner_id),
        title=TaskTitle(model.title),
        description=model.description,
        status=TaskStatus(model.status),
        created_at=as_utc(model.created_at),
        completed_at=as_utc(model.completed_at) if model.completed_at else None,
    )
