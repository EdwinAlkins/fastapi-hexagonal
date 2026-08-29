"""Agrégat ``Task`` — racine du bounded context.

L'entité porte les invariants métier et les transitions d'état. Elle ignore
totalement la persistance, le transport HTTP et tout framework.
"""

from __future__ import annotations

from datetime import UTC, datetime

from task_manager.domain.task.exceptions import TaskAlreadyCompleted
from task_manager.domain.task.value_objects import TaskId, TaskStatus, TaskTitle
from task_manager.domain.user.value_objects import UserId


def _now() -> datetime:
    return datetime.now(UTC)


class Task:
    """Tâche à réaliser, identifiée par un :class:`TaskId`."""

    def __init__(
        self,
        *,
        id: TaskId,
        owner_id: UserId,
        title: TaskTitle,
        description: str | None,
        status: TaskStatus,
        created_at: datetime,
        completed_at: datetime | None = None,
    ) -> None:
        self.id = id
        # Référence par identité vers l'agrégat User (côté « n » de la relation).
        self.owner_id = owner_id
        self.title = title
        self.description = description
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at

    @classmethod
    def create(cls, *, owner_id: UserId, title: TaskTitle, description: str | None = None) -> Task:
        """Factory : crée une nouvelle tâche à l'état ``TODO``, rattachée à un user."""
        return cls(
            id=TaskId.generate(),
            owner_id=owner_id,
            title=title,
            description=description,
            status=TaskStatus.TODO,
            created_at=_now(),
            completed_at=None,
        )

    def start(self) -> None:
        """Passe la tâche en cours. Sans effet si elle est déjà terminée."""
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyCompleted()
        self.status = TaskStatus.IN_PROGRESS

    def complete(self) -> None:
        """Marque la tâche comme terminée (invariant : pas deux fois)."""
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyCompleted()
        self.status = TaskStatus.DONE
        self.completed_at = _now()

    def rename(self, title: TaskTitle) -> None:
        """Renomme la tâche.

        Choix explicite : renommer est autorisé quel que soit le statut, y compris
        sur une tâche ``DONE`` (contrairement à ``start`` / ``complete``). Le titre
        est une donnée descriptive, pas une transition d'état ; corriger le libellé
        d'une tâche terminée reste légitime. Ajouter ici une garde ``TaskAlready
        Completed`` si le métier venait à l'interdire.
        """
        self.title = title

    def __eq__(self, other: object) -> bool:
        # Égalité par identité (entité, pas value object).
        return isinstance(other, Task) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
