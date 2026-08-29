"""Objets de transfert (commands & DTO) de la couche application.

Ce sont des structures neutres (dataclasses) qui découplent les use cases
des schémas Pydantic (présentation) et des value objects (domaine).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from task_manager.domain.task.entities import Task


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Données nécessaires à la création d'une tâche."""

    owner_id: str
    title: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class TaskDTO:
    """Représentation de sortie d'une tâche, indépendante du transport."""

    id: str
    owner_id: str
    title: str
    description: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_entity(cls, task: Task) -> TaskDTO:
        """Projette un agrégat du domaine en DTO de sortie."""
        return cls(
            id=str(task.id),
            owner_id=str(task.owner_id),
            title=str(task.title),
            description=task.description,
            status=task.status.value,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )


@dataclass(frozen=True, slots=True)
class ShareTaskNotification:
    """Données nécessaires au partage d'une tâche."""

    task_id: str
    user_ids: list[str]
    subject: str
    body: str
