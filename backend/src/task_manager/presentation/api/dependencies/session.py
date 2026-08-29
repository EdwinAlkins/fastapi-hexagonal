"""Frontière transactionnelle : session liée à la requête (câblage transverse)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Fournit une session transactionnelle liée à la requête.

    La frontière transactionnelle appartient à la requête (et non au
    repository) : commit si tout réussit, rollback à la moindre exception.
    Les repositories ne committent donc jamais eux-mêmes.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
