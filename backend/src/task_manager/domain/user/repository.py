"""Port de persistance des utilisateurs (interface, côté « driven »)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserId


class UserRepository(ABC):
    """Contrat de persistance de l'agrégat :class:`User`."""

    @abstractmethod
    async def save(self, user: User) -> None:
        """Persiste l'état de l'agrégat, qu'il soit nouveau ou modifié."""

    @abstractmethod
    async def get(self, user_id: UserId) -> User:
        """Récupère un utilisateur. Lève ``UserNotFound`` si absent."""

    @abstractmethod
    async def exists(self, user_id: UserId) -> bool:
        """Indique si un utilisateur existe (sans le charger entièrement)."""

    @abstractmethod
    async def find_by_email(self, email: Email) -> User | None:
        """Retourne l'utilisateur portant cette adresse, ou ``None``.

        Sert à vérifier l'unicité de l'e-mail avant création.
        """

    @abstractmethod
    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Retourne les utilisateurs, avec pagination (bornée)."""
