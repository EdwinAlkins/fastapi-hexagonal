"""Value objects du bounded context ``task``.

Les value objects sont immuables et s'auto-valident à la construction :
un objet existant est toujours dans un état valide (« always-valid domain model »).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from task_manager.domain.task.exceptions import EmptyTitle, InvalidTaskId, TitleTooLong


@dataclass(frozen=True, slots=True)
class TaskId:
    """Identité d'une tâche, encapsulant un UUID."""

    value: uuid.UUID

    @classmethod
    def generate(cls) -> TaskId:
        """Génère une nouvelle identité unique, croissante dans le temps.

        UUIDv7 plutôt que v4 : ses 48 bits de poids fort sont un timestamp, donc
        les identités successives sont ordonnées. Les insertions se font en fin
        d'index B-tree au lieu de se disperser, ce qui évite la fragmentation
        (page splits, amplification WAL) sur une table qui grossit — tout en
        gardant une identité générée par le domaine, sans aller-retour en base.
        """
        return cls(uuid.uuid7())

    @classmethod
    def from_string(cls, raw: str) -> TaskId:
        """Reconstruit une identité depuis sa représentation textuelle.

        Lève :class:`InvalidTaskId` (erreur métier) plutôt qu'une ``ValueError``
        brute lorsque la chaîne n'est pas un UUID valide.
        """
        try:
            return cls(uuid.UUID(raw))
        except ValueError as exc:
            raise InvalidTaskId(raw) from exc

    def __str__(self) -> str:
        return str(self.value)


TITLE_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class TaskTitle:
    """Titre de tâche : non vide, borné en longueur, sans espaces superflus."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        if not cleaned:
            raise EmptyTitle()
        if len(cleaned) > TITLE_MAX_LENGTH:
            raise TitleTooLong(TITLE_MAX_LENGTH)
        # Normalise la valeur (frozen : contournement via object.__setattr__).
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


class TaskStatus(StrEnum):
    """Cycle de vie d'une tâche."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
