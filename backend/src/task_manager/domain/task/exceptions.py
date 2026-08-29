"""Exceptions métier du bounded context ``task``."""

from __future__ import annotations

from task_manager.domain.shared.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


class EmptyTitle(ValidationError):
    """Le titre d'une tâche est vide ou uniquement composé d'espaces."""

    def __init__(self) -> None:
        super().__init__("Le titre de la tâche ne peut pas être vide.")


class TitleTooLong(ValidationError):
    """Le titre dépasse la longueur maximale autorisée."""

    def __init__(self, max_length: int) -> None:
        super().__init__(f"Le titre ne peut pas dépasser {max_length} caractères.")


class InvalidTaskId(ValidationError):
    """L'identifiant de tâche fourni n'est pas un UUID valide."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__(f"Identifiant de tâche invalide : {raw!r}.")


class TaskAlreadyCompleted(ConflictError):
    """Tentative de compléter une tâche déjà terminée."""

    def __init__(self) -> None:
        super().__init__("La tâche est déjà terminée.")


class TaskNotFound(NotFoundError):
    """Aucune tâche ne correspond à l'identifiant demandé."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Aucune tâche trouvée pour l'identifiant {task_id}.")
