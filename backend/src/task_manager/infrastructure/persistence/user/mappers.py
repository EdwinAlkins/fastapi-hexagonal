"""Conversion entre l'agrégat ``User`` et son modèle ORM."""

from __future__ import annotations

from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserId, UserName
from task_manager.infrastructure.persistence.converters import as_utc
from task_manager.infrastructure.persistence.user.models import UserModel


def to_model(user: User) -> UserModel:
    """Domaine → ORM (nouvelle ligne)."""
    return UserModel(
        id=user.id.value,
        name=str(user.name),
        email=str(user.email),
        created_at=user.created_at,
    )


def apply_to_model(model: UserModel, user: User) -> None:
    """Domaine → ORM (mise à jour en place). ``id`` et ``created_at`` immuables."""
    model.name = str(user.name)
    model.email = str(user.email)


def to_domain(model: UserModel) -> User:
    """ORM → domaine."""
    return User(
        id=UserId(model.id),
        name=UserName(model.name),
        email=Email(model.email),
        created_at=as_utc(model.created_at),
    )
