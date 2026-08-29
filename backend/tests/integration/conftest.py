"""Fixtures des tests d'intégration : application montée sur un PostgreSQL et un
Valkey jetables (testcontainers).

Les tests d'intégration visent les moteurs réels (via testcontainers) et non des
substituts : le dialecte SQL, les types (``uuid``, ``timestamptz``), les
contraintes (unicité, FK ``ON DELETE CASCADE``) et le cache sont ceux de la
production. Lancer ces tests requiert donc un démon Docker.

Les conteneurs sont aussi ce qui rend la suite **hermétique** : sans eux, un
Redis qui écouterait sur le port par défaut de la machine (la stack
``docker compose`` du projet, par exemple) serait utilisé par les tests, qui
liraient alors des entrées laissées par un run précédent.

Le schéma est créé/détruit à chaque test (create_all / drop_all) → isolation
totale, sans dépendre de l'ordre d'exécution. ``session_factory`` est la fixture
pivot que partagent le ``client`` *et* les fixtures de seed : tous écrivent et
lisent la même base. Les données de départ sont d'ailleurs semées via les use
cases (chemin d'écriture réel), jamais en SQL brut.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from task_manager.application.shared.messaging import EventPublisherPort
from task_manager.application.task.dto import CreateTaskCommand, TaskDTO
from task_manager.application.task.use_cases.create_task import CreateTask
from task_manager.application.user.dto import CreateUserCommand, UserDTO
from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.infrastructure.config import Settings
from task_manager.infrastructure.persistence.database import (
    Base,
    create_engine,
    create_session_factory,
    init_db,
)
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository
from task_manager.presentation.api.app import create_app
from task_manager.presentation.api.dependencies import get_session


class _NoOpMessageAdapter(EventPublisherPort):
    """Adapter messaging inerte pour les tests d'API (pas de broker réel)."""

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        return None


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Démarre un PostgreSQL jetable, partagé par toute la session de tests."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Démarre un Valkey jetable, partagé par toute la session de tests.

    Même image qu'en production : Valkey parle le protocole Redis, donc
    ``RedisContainer`` (et ``redis.asyncio``) s'y connectent tels quels.
    """
    with RedisContainer("valkey/valkey:8-alpine") as valkey:
        host = valkey.get_container_host_ip()
        port = valkey.get_exposed_port(valkey.port)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
async def session_factory(
    database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Moteur + schéma neufs par test : create_all au setup, drop_all au teardown.

    Fixture pivot partagée par ``client`` et les fixtures de seed → tous écrivent
    et lisent la même base. ``init_db`` enregistre au passage les modèles ORM sur
    ``Base.metadata``, ce dont le ``drop_all`` du teardown a besoin.
    """
    engine = create_engine(SecretStr(database_url))
    await init_db(engine)
    try:
        yield create_session_factory(engine)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def client(
    database_url: str,
    redis_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    # ``init_db=False`` : le schéma est déjà posé par ``session_factory``. Le
    # moteur interne de l'app n'est jamais sollicité (``get_session`` surchargé
    # ci-dessous), mais on lui passe la vraie URL par sûreté.
    app = create_app(
        settings=Settings(
            database_url=SecretStr(database_url),
            redis_url=SecretStr(redis_url),
            # Factice : l'adapter est aussitôt remplacé par le NoOp (aucune connexion).
            rabbitmq_url=SecretStr("amqp://guest:guest@localhost:5672/"),
            init_db=False,
        )
    )
    # Avant le lifespan ASGI : évite une connexion RabbitMQ réelle en CI/local.
    app.state.message_adapter = _NoOpMessageAdapter()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        # Reproduit la frontière transactionnelle de production (commit/rollback),
        # sur la même fabrique de sessions que les fixtures de seed.
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    # Le conteneur Valkey vit le temps de la session : on vide le cache entre deux
    # tests pour qu'aucune entrée ne fuite de l'un à l'autre.
    async with Redis.from_url(redis_url) as redis:
        await redis.flushall()


@pytest.fixture
async def cache(redis_url: str) -> AsyncIterator[Redis]:
    """Accès direct au cache, pour inspecter ce que l'API y écrit."""
    async with Redis.from_url(redis_url, decode_responses=True) as redis:
        yield redis


@pytest.fixture
async def seeded_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> UserDTO:
    """Insère un utilisateur connu (Ada Lovelace) via le use case ``CreateUser``."""
    command = CreateUserCommand(name="Ada Lovelace", email="ada@example.com")
    async with session_factory() as session:
        user = await CreateUser(SqlAlchemyUserRepository(session)).execute(command)
        await session.commit()
    return user


@pytest.fixture
async def seeded_tasks(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_user: UserDTO,
) -> list[TaskDTO]:
    """Insère trois tâches connues rattachées à ``seeded_user`` via ``CreateTask``."""
    titles = ["Rédiger la doc", "Relire la PR", "Déployer"]
    async with session_factory() as session:
        use_case = CreateTask(
            SqlAlchemyTaskRepository(session),
            SqlAlchemyUserRepository(session),
        )
        tasks = [
            await use_case.execute(CreateTaskCommand(owner_id=seeded_user.id, title=title))
            for title in titles
        ]
        await session.commit()
    return tasks
