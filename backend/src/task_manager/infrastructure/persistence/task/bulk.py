"""Implémentation SQLAlchemy de l'écriture en masse des tâches."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.application.task.bulk import TaskBulkWriterPort
from task_manager.domain.task.entities import Task
from task_manager.infrastructure.persistence.task.models import TaskModel


class SqlAlchemyTaskBulkWriter(TaskBulkWriterPort):
    """Un ``INSERT`` multi-lignes par lot, au lieu d'un aller-retour par tâche.

    Trois écarts assumés avec ``SqlAlchemyTaskRepository`` :

    - **Pas de lecture préalable.** ``save`` fait un ``session.get`` pour choisir
      entre insertion et mise à jour ; ici on sait que l'on insère, et ``ON
      CONFLICT`` tranche côté base — un aller-retour par ligne économisé.
    - **Pas d'unité de travail ORM.** On passe par le *core* plutôt que par
      ``session.add`` : aucune instance n'est suivie, donc l'identity map ne gonfle
      pas au fil des lots.
    - **Dialecte PostgreSQL explicite.** ``ON CONFLICT`` n'est pas du SQL portable.
      C'est le prix, et il se paie dans l'infrastructure — le port, lui, reste neutre.

    Les identités venant du domaine (UUIDv7), le lot entier se construit en mémoire
    avant de toucher la base : ni ``RETURNING``, ni aller-retour pour apprendre un
    identifiant. Et le préfixe temporel maintient les insertions au bord droit de
    l'index, là où un ``uuid4`` fragmenterait le B-tree sur un gros import.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_all(self, tasks: Sequence[Task]) -> BulkWriteResult:
        if not tasks:
            return BulkWriteResult.empty()

        statement = pg_insert(TaskModel).values(
            [
                {
                    "id": task.id.value,
                    "owner_id": task.owner_id.value,
                    "title": str(task.title),
                    "description": task.description,
                    "status": task.status.value,
                    "created_at": task.created_at,
                    "completed_at": task.completed_at,
                }
                for task in tasks
            ]
        )
        # ``execute`` est typé ``Result`` ; un ``INSERT`` renvoie en réalité un
        # ``CursorResult``, seul porteur de ``rowcount``.
        result = cast(
            "CursorResult[None]",
            await self._session.execute(statement.on_conflict_do_nothing()),
        )
        # ``rowcount`` compte les lignes réellement insérées : le reste a été ignoré
        # parce qu'il existait déjà. C'est ce qui rend l'import rejouable.
        inserted = result.rowcount
        return BulkWriteResult(inserted=inserted, skipped=len(tasks) - inserted)
