"""Objets de transfert (commands & DTO) de la couche application — contexte ``user``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from task_manager.domain.user.entities import User


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    """Données nécessaires à la création d'un utilisateur."""

    name: str
    email: str


@dataclass(frozen=True, slots=True)
class UserDTO:
    """Représentation de sortie d'un utilisateur, indépendante du transport."""

    id: str
    name: str
    email: str
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        """Projette un agrégat du domaine en DTO de sortie."""
        return cls(
            id=str(user.id),
            name=str(user.name),
            email=str(user.email),
            created_at=user.created_at,
        )
