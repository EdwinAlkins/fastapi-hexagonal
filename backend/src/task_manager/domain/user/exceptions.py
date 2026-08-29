"""Exceptions métier du bounded context ``user``."""

from __future__ import annotations

from task_manager.domain.shared.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


class EmptyName(ValidationError):
    """Le nom d'un utilisateur est vide ou uniquement composé d'espaces."""

    def __init__(self) -> None:
        super().__init__("Le nom de l'utilisateur ne peut pas être vide.")


class NameTooLong(ValidationError):
    """Le nom dépasse la longueur maximale autorisée."""

    def __init__(self, max_length: int) -> None:
        super().__init__(f"Le nom ne peut pas dépasser {max_length} caractères.")


class InvalidEmail(ValidationError):
    """L'adresse e-mail fournie n'a pas un format valide."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__(f"Adresse e-mail invalide : {raw!r}.")


class InvalidUserId(ValidationError):
    """L'identifiant d'utilisateur fourni n'est pas un UUID valide."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__(f"Identifiant d'utilisateur invalide : {raw!r}.")


class UserNotFound(NotFoundError):
    """Aucun utilisateur ne correspond à l'identifiant demandé."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"Aucun utilisateur trouvé pour l'identifiant {user_id}.")


class EmailAlreadyUsed(ConflictError):
    """Un utilisateur possède déjà cette adresse e-mail (contrainte d'unicité)."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"L'adresse e-mail {email!r} est déjà utilisée.")
