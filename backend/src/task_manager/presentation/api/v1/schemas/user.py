"""Schémas Pydantic du contexte ``user`` — contrat HTTP (frontière uniquement)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from task_manager.application.user.dto import UserDTO
from task_manager.domain.user.value_objects import NAME_MAX_LENGTH


class CreateUserRequest(BaseModel):
    """Corps de requête pour la création d'un utilisateur."""

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH, examples=["Ada Lovelace"])
    email: str = Field(..., examples=["ada@example.com"])


class UpdateUserRequest(BaseModel):
    """Corps de requête pour le renommage d'un utilisateur."""

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH, examples=["Grace Hopper"])


class UserResponse(BaseModel):
    """Représentation d'un utilisateur renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: UserDTO) -> UserResponse:
        return cls.model_validate(dto)
