"""Agrégat ``User`` — racine du bounded context ``user``.

Un utilisateur possède des tâches (relation 1→n), mais l'agrégat ne charge
*jamais* ses tâches : chaque agrégat a sa propre frontière de cohérence. La
navigation « user → ses tâches » est une requête servie par le contexte ``task``
(``TaskRepository.list_by_owner``), pas une collection portée par ``User``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from task_manager.domain.user.value_objects import Email, UserId, UserName


def _now() -> datetime:
    return datetime.now(UTC)


class User:
    """Utilisateur du système, identifié par un :class:`UserId`."""

    def __init__(
        self,
        *,
        id: UserId,
        name: UserName,
        email: Email,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.name = name
        self.email = email
        self.created_at = created_at

    @classmethod
    def create(cls, *, name: UserName, email: Email) -> User:
        """Factory : crée un nouvel utilisateur."""
        return cls(
            id=UserId.generate(),
            name=name,
            email=email,
            created_at=_now(),
        )

    def rename(self, name: UserName) -> None:
        """Change le nom d'affichage de l'utilisateur."""
        self.name = name

    def __eq__(self, other: object) -> bool:
        # Égalité par identité (entité, pas value object).
        return isinstance(other, User) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
