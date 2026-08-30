"""Implémentation SQLAlchemy du chemin de lecture (``TaskQueryPort``).

Tout ce qui parle SQL vit dans l'infrastructure : le port en ``application/``
ignore jusqu'à l'existence d'une jointure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.task.queries import TaskQueryPort, TaskWithOwner
from task_manager.infrastructure.persistence.task.models import TaskModel
from task_manager.infrastructure.persistence.user.models import UserModel

# Taille des lots remontés par le curseur serveur. Compromis classique : plus le
# lot est grand, moins il y a d'allers-retours, mais plus le pic mémoire monte.
_BATCH = 500


class SqlAlchemyTaskQueryService(TaskQueryPort):
    """Lit les tâches et leur propriétaire en **une** requête, sans agrégat."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]:
        """Une seule requête, un curseur serveur, une mémoire constante.

        ``yield_per`` fait remonter les lignes par lots au lieu de tout charger :
        c'est ce qui rend l'export insensible au volume. Le curseur vit **dans** la
        transaction de la requête, ce qui reste compatible avec PgBouncer en mode
        transaction (seuls les curseurs ``WITH HOLD``, qui survivent au commit, y
        sont interdits).
        """
        statement = (
            select(
                TaskModel.id,
                TaskModel.title,
                TaskModel.description,
                TaskModel.status,
                TaskModel.created_at,
                TaskModel.completed_at,
                UserModel.id.label("owner_id"),
                UserModel.name.label("owner_name"),
                UserModel.email.label("owner_email"),
            )
            .join(UserModel, TaskModel.owner_id == UserModel.id)
            .order_by(TaskModel.created_at)
            .execution_options(yield_per=_BATCH)
        )
        result = await self._session.stream(statement)
        async for row in result:
            yield TaskWithOwner(
                task_id=str(row.id),
                title=row.title,
                description=row.description,
                status=row.status,
                created_at=row.created_at,
                completed_at=row.completed_at,
                owner_id=str(row.owner_id),
                owner_name=row.owner_name,
                owner_email=row.owner_email,
            )

    async def count(self) -> int:
        """``COUNT`` côté base — jamais ``len()`` sur une liste chargée."""
        total = await self._session.scalar(select(func.count()).select_from(TaskModel))
        return int(total or 0)
