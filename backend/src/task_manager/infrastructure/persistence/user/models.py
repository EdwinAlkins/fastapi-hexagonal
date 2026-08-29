"""Modèle ORM du bounded context ``user`` (côté « 1 » de la relation)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from task_manager.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    # Import réservé au typage : cible résolue par nom via le registry SQLAlchemy.
    from task_manager.infrastructure.persistence.task.models import TaskModel


class UserModel(Base):
    """Ligne de la table ``users`` (côté « 1 » de la relation)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # ``unique`` : la contrainte d'unicité de l'e-mail est aussi garantie en base.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    # ``server_default`` : filet de sécurité si l'application omet ``created_at``.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Côté « 1 » de la relation. Purement technique (ORM) : n'existe pas dans le
    # domaine, où User ne porte pas la collection de ses tâches. Chargement
    # jamais implicite en mode async — préférer un ``selectinload`` explicite.
    tasks: Mapped[list[TaskModel]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
