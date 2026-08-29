"""Schémas Pydantic du contexte ``task`` — contrat HTTP (frontière uniquement)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from task_manager.application.task.dto import TaskDTO
from task_manager.domain.task.value_objects import TITLE_MAX_LENGTH


class CreateTaskRequest(BaseModel):
    """Corps de requête pour la création d'une tâche."""

    # ``max_length`` référence la constante du domaine : une seule source de vérité.
    title: str = Field(
        ..., min_length=1, max_length=TITLE_MAX_LENGTH, examples=["Rédiger le rapport"]
    )
    description: str | None = Field(default=None, examples=["Section 1 à 3"])


class UpdateTaskRequest(BaseModel):
    """Corps de requête pour le renommage d'une tâche."""

    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LENGTH, examples=["Titre corrigé"])


class TaskResponse(BaseModel):
    """Représentation d'une tâche renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    title: str
    description: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: TaskDTO) -> TaskResponse:
        return cls.model_validate(dto)


class ShareTaskRequest(BaseModel):
    """Corps de requête pour le partage d'une tâche."""

    user_ids: list[str] = Field(..., examples=[["123e4567-e89b-12d3-a456-426614174000"]])
    subject: str = Field(..., examples=["Tâche partagée"])
    body: str = Field(..., examples=["La tâche a été partagée avec vous."])
