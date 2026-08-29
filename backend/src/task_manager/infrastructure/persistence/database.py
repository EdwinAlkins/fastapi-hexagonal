"""Configuration de la base de données (SQLAlchemy async / PostgreSQL)."""

from __future__ import annotations

from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles ORM."""


def create_engine(
    database_url: SecretStr,
    *,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
) -> AsyncEngine:
    """Crée le moteur asynchrone (PostgreSQL / asyncpg).

    ``pool_size`` / ``max_overflow`` proviennent de ``Settings`` (défauts ici pour
    les appels sans configuration, ex. tests) : le pool SQLAlchemy se cumule avec
    le pool PgBouncer placé devant Postgres, il doit donc rester dimensionnable.

    Deux réglages sont dictés par PgBouncer en mode ``transaction``, où une
    connexion serveur n'est prêtée que le temps d'une transaction :

    - ``pool_pre_ping`` : une connexion recyclée côté pooler est détectée et
      remplacée avant usage plutôt que de faire échouer la requête ;
    - ``prepared_statement_name_func`` : asyncpg nomme ses prepared statements
      de façon incrémentale, or deux clients multiplexés sur la même connexion
      serveur se marcheraient dessus (``DuplicatePreparedStatementError``). Un
      nom unique par statement supprime la collision. Le cache, lui, se
      désactive via ``prepared_statement_cache_size=0`` dans l'URL.
    """
    return create_async_engine(
        database_url.get_secret_value(),
        echo=echo,
        future=True,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        # Un nom unique par prepared statement (cf. docstring).
        connect_args={"prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__"},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Crée la fabrique de sessions liée au moteur."""
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Crée le schéma (``create_all``).

    Utile en dev local (``APP_INIT_DB=true``) et dans les tests. En prod /
    Docker, Alembic (``alembic upgrade head``) pilote le schéma.

    Importe les modèles de chaque contexte pour qu'ils soient enregistrés sur
    ``Base.metadata`` (et que le registry SQLAlchemy résolve les relations).
    """
    from task_manager.infrastructure.persistence.task import models as task_models  # noqa: F401
    from task_manager.infrastructure.persistence.user import models as user_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
