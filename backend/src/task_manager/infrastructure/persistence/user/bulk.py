"""Implémentation SQLAlchemy de l'écriture en masse des utilisateurs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.application.user.bulk import UserBulkWriterPort
from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import UserId
from task_manager.infrastructure.persistence.user.models import UserModel


class SqlAlchemyUserBulkWriter(UserBulkWriterPort):
    """Un ``INSERT`` multi-lignes par lot, tolérant aux utilisateurs déjà connus."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_all(self, users: Sequence[User]) -> BulkWriteResult:
        if not users:
            return BulkWriteResult.empty()

        statement = pg_insert(UserModel).values(
            [
                {
                    "id": user.id.value,
                    "name": str(user.name),
                    "email": str(user.email),
                    "created_at": user.created_at,
                }
                for user in users
            ]
        )
        # ``on_conflict_do_nothing()`` **sans cible** : il couvre aussi bien la clé
        # primaire que l'unicité de l'e-mail. Viser explicitement ``id`` laisserait
        # un e-mail déjà pris lever une ``IntegrityError`` et emporter tout le lot.
        # ``execute`` est typé ``Result`` ; un ``INSERT`` renvoie en réalité un
        # ``CursorResult``, seul porteur de ``rowcount``.
        result = cast(
            "CursorResult[None]",
            await self._session.execute(statement.on_conflict_do_nothing()),
        )
        inserted = result.rowcount
        return BulkWriteResult(inserted=inserted, skipped=len(users) - inserted)

    async def existing_ids(self, user_ids: Sequence[UserId]) -> set[UserId]:
        if not user_ids:
            return set()
        rows = await self._session.scalars(
            select(UserModel.id).where(UserModel.id.in_([uid.value for uid in user_ids]))
        )
        return {UserId(value) for value in rows}
