"""Adaptateur de persistance : implémentation SQLAlchemy du port ``UserRepository``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import Email, UserId
from task_manager.infrastructure.persistence.user import mappers
from task_manager.infrastructure.persistence.user.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    """Persiste les utilisateurs via SQLAlchemy async.

    Mêmes règles que le repository des tâches : aucune méthode ne committe, la
    transaction est pilotée par la requête (``get_session``).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> None:
        existing = await self._session.get(UserModel, user.id.value)
        if existing is None:
            self._session.add(mappers.to_model(user))
        else:
            mappers.apply_to_model(existing, user)

    async def get(self, user_id: UserId) -> User:
        model = await self._session.get(UserModel, user_id.value)
        if model is None:
            raise UserNotFound(str(user_id))
        return mappers.to_domain(model)

    async def exists(self, user_id: UserId) -> bool:
        # ``SELECT id ... LIMIT 1`` : on ne charge pas la ligne, seule la présence
        # nous intéresse (même stratégie que ``SqlAlchemyTaskRepository.exists``).
        stmt = select(UserModel.id).where(UserModel.id == user_id.value).limit(1)
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def find_by_email(self, email: Email) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == str(email)))
        model = result.scalar_one_or_none()
        return mappers.to_domain(model) if model is not None else None

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self._session.execute(
            select(UserModel).order_by(UserModel.created_at).limit(limit).offset(offset)
        )
        return [mappers.to_domain(model) for model in result.scalars().all()]
