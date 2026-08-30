"""Adaptateur de persistance : implémentation SQLAlchemy du port ``UserRepository``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import EmailAlreadyUsed, UserNotFound
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import Email, UserId
from task_manager.infrastructure.persistence.user import mappers
from task_manager.infrastructure.persistence.user.models import UserModel

# ``users.email`` est déclarée ``unique=True, index=True`` : SQLAlchemy en fait un
# **index unique** nommé ``ix_users_email`` — pas une contrainte ``users_email_key``,
# ce que produirait un ``unique=True`` seul. La migration Alembic emploie le même nom
# (``001_initial_schema``), donc tests et production parlent bien du même objet.
# Le viser explicitement évite de traduire en « e-mail déjà pris » une violation qui
# porterait en réalité sur une autre contrainte.
_CONTRAINTE_EMAIL = "ix_users_email"


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
        await self._flush(user)

    async def _flush(self, user: User) -> None:
        """Envoie l'écriture **maintenant**, et traduit un conflit d'unicité.

        Sans ce ``flush``, l'``INSERT`` ne partirait qu'au ``commit`` — c'est-à-dire
        dans la fermeture de la dépendance de session, **après** que la réponse a
        été construite. Une violation de contrainte y est alors invisible pour
        l'appelant : mesuré sur ce projet, le client reçoit un ``201`` complet, avec
        l'identifiant du user dans le corps, alors que la transaction est annulée et
        que rien n'a été écrit. Un 500 serait déjà mauvais ; un succès mensonger est
        pire.

        ``CreateUser`` vérifie déjà l'unicité avant d'écrire. Ce contrôle reste
        utile — il évite l'exception dans le cas courant et donne un message net —
        mais il ne peut pas être atomique : entre sa lecture et l'écriture, une
        autre transaction peut prendre l'adresse. La contrainte d'unicité est le
        seul arbitre fiable ; ce bloc est ce qui la rend audible côté métier.

        Traduire ici est le rôle de l'adaptateur, pas une entorse : le repository
        rend déjà ``UserNotFound`` plutôt qu'un ``None`` technique.
        """
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _CONTRAINTE_EMAIL in str(exc.orig):
                raise EmailAlreadyUsed(str(user.email)) from exc
            raise

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
