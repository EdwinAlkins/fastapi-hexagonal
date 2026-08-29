"""Modèle ORM du bounded context ``task`` (côté « n » de la relation).

Modèle volontairement distinct de l'agrégat du domaine : la conversion est
assurée par les mappers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from task_manager.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    # Import réservé au typage : la cible de la relation est résolue à l'exécution
    # par nom, via le registry SQLAlchemy (les deux modèles partagent ``Base``).
    from task_manager.infrastructure.persistence.user.models import UserModel


class TaskModel(Base):
    """Ligne de la table ``tasks`` (côté « n » de la relation)."""

    __tablename__ = "tasks"

    # Type ``Uuid`` : colonne ``uuid`` native côté PostgreSQL.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    # Clé étrangère vers ``users`` : matérialise ``Task.owner_id`` en base.
    # Référencée par nom de table (string) → aucun import du modèle User requis.
    # ``ondelete=CASCADE`` : supprimer un user supprime ses tâches.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # ``status`` filtré, ``created_at`` trié/paginé → indexés.
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # ``server_default`` : filet de sécurité si l'application omet ``created_at``.
    # En pratique le domaine le renseigne toujours (``_now()``).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[UserModel] = relationship(back_populates="tasks")
