"""Agrégat ``Task`` — racine du bounded context.

L'entité porte les invariants métier et les transitions d'état. Elle ignore
totalement la persistance, le transport HTTP et tout framework.
"""

from __future__ import annotations

from datetime import UTC, datetime

from task_manager.domain.task.exceptions import InconsistentTaskState, TaskAlreadyCompleted
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

    @classmethod
    def reconstitute(
        cls,
        *,
        id: TaskId,
        owner_id: UserId,
        title: TaskTitle,
        description: str | None,
        status: TaskStatus,
        created_at: datetime,
        completed_at: datetime | None,
    ) -> Task:
        """Reconstruit une tâche **qui existe déjà**, dans l'état où elle était.

        À ne pas confondre avec :meth:`create`, et la distinction n'est pas
        cosmétique :

        - ``create`` répond à « **cet état est-il atteignable ?** » : elle impose un
          identifiant neuf, le statut ``TODO`` et l'instant présent. Elle ne sait
          donc pas représenter une tâche importée qui serait déjà terminée.
        - ``reconstitute`` répond à « **cet état est-il valide ?** » : elle accepte
          n'importe quel état de la machine, à condition qu'il soit cohérent.

        C'est la porte des imports et des restaurations. Les invariants de champ
        restent assurés par les value objects (un titre vide est refusé ici comme
        ailleurs) ; ce qui n'est pas rejoué, ce sont les règles de **transition**,
        qui portent sur des changements d'état et n'ont pas de sens sur un état au
        repos.

        Cette méthode est délibérément plus stricte que ``mappers.to_domain`` :
        celui-ci relit *notre* base, dont nous sommes la source de vérité, alors
        qu'un import relit un fichier dont nous ne garantissons rien.
        """
        if status is TaskStatus.DONE and completed_at is None:
            raise InconsistentTaskState("une tâche terminée doit porter une date de complétion")
        if status is not TaskStatus.DONE and completed_at is not None:
            raise InconsistentTaskState(
                "une tâche non terminée ne peut pas porter de date de complétion"
            )
        if completed_at is not None and completed_at < created_at:
            raise InconsistentTaskState("la complétion précède la création")
        return cls(
            id=id,
            owner_id=owner_id,
            title=title,
            description=description,
            status=status,
            created_at=created_at,
            completed_at=completed_at,
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
