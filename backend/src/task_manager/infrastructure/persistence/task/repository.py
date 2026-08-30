"""Adaptateur de persistance : implémentation SQLAlchemy du port ``TaskRepository``."""

from __future__ import annotations

from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.domain.task.entities import Task
from task_manager.domain.task.exceptions import TaskNotFound
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.value_objects import UserId
from task_manager.infrastructure.persistence.task import mappers
from task_manager.infrastructure.persistence.task.models import TaskModel

# ``tasks.owner_id`` porte une clé étrangère déclarée sans nom explicite, dans le
# modèle comme dans la migration ``001_initial_schema`` : PostgreSQL la nomme donc
# lui-même, selon sa convention ``<table>_<colonne>_fkey``. Les deux chemins de
# création du schéma — ``create_all`` en test, Alembic en production — lui laissent
# ce choix, ils désignent bien le même objet. La viser explicitement évite de
# traduire en « propriétaire inconnu » une violation portant sur autre chose.
_CONTRAINTE_OWNER = "tasks_owner_id_fkey"


class SqlAlchemyTaskRepository(TaskRepository):
    """Persiste les tâches dans une base relationnelle via SQLAlchemy async.

    Aucune méthode ne committe : la transaction est pilotée par la requête
    (voir ``get_session``). On se contente ici de muter l'unité de travail.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, task: Task) -> None:
        # Insertion explicite si nouvelle, mise à jour en place sinon.
        # On évite ``merge`` (comportement implicite, SELECT superflu). Le
        # ``get`` ci-dessous est un compromis assumé : un SELECT même pour un
        # nouvel agrégat, en échange d'un upsert lisible et sans dépendance à un
        # flag ``is_persisted`` porté par l'entité de domaine.
        existing = await self._session.get(TaskModel, task.id.value)
        if existing is None:
            self._session.add(mappers.to_model(task))
        else:
            mappers.apply_to_model(existing, task)
        await self._flush(task)

    async def _flush(self, task: Task) -> None:
        """Envoie l'écriture **maintenant**, et traduit un propriétaire disparu.

        Même raisonnement que ``SqlAlchemyUserRepository._flush``, appliqué à la
        clé étrangère plutôt qu'à l'unicité. Sans ce ``flush``, l'``INSERT`` ne
        partirait qu'au ``commit``, donc après la construction de la réponse : le
        client recevrait un ``201`` complet pour une transaction annulée.

        ``CreateTask`` vérifie déjà l'existence du propriétaire avant d'écrire.
        Ce contrôle reste utile — il évite l'exception dans le cas courant et
        donne un message net — mais il n'est pas atomique : entre sa lecture et
        l'écriture, une autre transaction peut supprimer l'utilisateur (et la
        table déclare ``ondelete=CASCADE``, donc rien ne retient la suppression).
        La clé étrangère est le seul arbitre fiable ; ce bloc est ce qui la rend
        audible côté métier.
        """
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _CONTRAINTE_OWNER in str(exc.orig):
                raise UserNotFound(str(task.owner_id)) from exc
            raise

    async def get(self, task_id: TaskId) -> Task:
        model = await self._session.get(TaskModel, task_id.value)
        if model is None:
            raise TaskNotFound(str(task_id))
        return mappers.to_domain(model)

    # Déclarée avant ``list`` : évite que l'annotation ``list[Task]`` ne résolve
    # vers la méthode ``list`` (shadowing du builtin) — cf. le port.
    async def list_by_owner(
        self, owner_id: UserId, *, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        # Cœur de la relation 1→n : simple filtre sur la clé étrangère (indexée).
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.owner_id == owner_id.value)
            .order_by(TaskModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.to_domain(model) for model in result.scalars().all()]

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[Task]:
        result = await self._session.execute(
            select(TaskModel).order_by(TaskModel.created_at).limit(limit).offset(offset)
        )
        return [mappers.to_domain(model) for model in result.scalars().all()]

    async def delete(self, task_id: TaskId) -> None:
        # ``DELETE ... WHERE id = ?`` direct : inutile de charger la ligne pour
        # la supprimer. ``rowcount`` distingue la suppression effective de la
        # tâche absente.
        # ``execute`` est typé ``Result`` ; un ``DELETE`` renvoie en réalité un
        # ``CursorResult`` qui porte ``rowcount``.
        result = cast(
            "CursorResult[None]",
            await self._session.execute(delete(TaskModel).where(TaskModel.id == task_id.value)),
        )
        if result.rowcount == 0:
            raise TaskNotFound(str(task_id))

    async def exists(self, task_id: TaskId) -> bool:
        stmt = select(TaskModel.id).where(TaskModel.id == task_id.value).limit(1)
        result = await self._session.execute(stmt)
        return result.first() is not None
