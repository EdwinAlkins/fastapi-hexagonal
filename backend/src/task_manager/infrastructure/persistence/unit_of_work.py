"""Adaptateur du port ``UnitOfWorkPort``."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.shared.unit_of_work import UnitOfWorkPort


class SqlAlchemyUnitOfWork(UnitOfWorkPort):
    """Committe la session courante.

    C'est la seule classe du dépôt, hors adaptateurs driving, à committer — et
    c'est délibérément explicite : un use case qui veut ce pouvoir doit le demander
    par un port, il ne l'obtient jamais par effet de bord d'un repository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()
