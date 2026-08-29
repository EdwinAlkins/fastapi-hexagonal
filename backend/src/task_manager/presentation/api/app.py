"""Fabrique de l'application FastAPI (composition root)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from sqlalchemy import text

from task_manager.infrastructure.config import Settings, get_settings
from task_manager.infrastructure.logging import configure_logging
from task_manager.infrastructure.mail.smtp import SMTPEmailSenderAdapter
from task_manager.infrastructure.messaging.rabbitmq import RabbitMQMessageAdapter
from task_manager.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    init_db,
)
from task_manager.presentation.api.dependencies import CachePortDep, SessionDep
from task_manager.presentation.api.error_handlers import register_error_handlers
from task_manager.presentation.api.middleware import register_request_logging
from task_manager.presentation.api.v1.routers import tasks, users

logger = logging.getLogger("task_manager")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construit et configure l'application.

    Passer ``settings`` explicitement facilite les tests (ex. base jetable).
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    # Ne jamais journaliser ``settings`` en entier : les URL de base et de cache
    # portent des identifiants (les ``SecretStr`` les masquent, mais un futur
    # champ en clair fuiterait sans bruit).
    logger.info("Démarrage de %s", settings.app_name)
    engine = create_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    message_adapter = RabbitMQMessageAdapter(
        settings.rabbitmq_url.get_secret_value(),
        settings.exchange_name,
    )
    # Adaptateur SMTP mutualisé (sans état, thread-safe) : une seule instance pour
    # tout le process plutôt qu'une par requête.
    smtp_sender = SMTPEmailSenderAdapter(settings.smtp_host, settings.smtp_port)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.init_db:
            logger.info("Initialisation du schéma de base de données (create_all).")
            await init_db(engine)
        # Via ``app.state`` pour que les tests puissent substituer l'adapter
        # avant l'entrée dans le lifespan (ASGITransport).
        await app.state.message_adapter.connect()
        try:
            yield
        finally:
            await app.state.message_adapter.close()
            await engine.dispose()
            await redis.aclose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    Instrumentator().instrument(app).expose(app)
    app.state.settings = settings
    # Configuration de la base de données
    app.state.engine = engine
    app.state.session_factory = session_factory
    # Configuration du Cache
    app.state.redis = redis
    # Configuration du Message Adapter (connecté au lifespan)
    app.state.message_adapter = message_adapter
    # Configuration du SMTP (instance unique réutilisée par toutes les requêtes)
    app.state.smtp_sender = smtp_sender

    register_error_handlers(app)
    register_request_logging(app)
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness(session: SessionDep, cache: CachePortDep) -> dict[str, str]:
        # Readiness = dépendances *critiques pour servir une requête HTTP* : la
        # base et le cache. Le broker RabbitMQ en est délibérément exclu — l'API
        # publie de façon asynchrone, une lecture GET reste servie s'il est down.
        # C'est au worker (consumer) de porter un readiness qui vérifie le broker.
        await session.execute(text("SELECT 1"))
        if not await cache.ping():
            raise HTTPException(503, "cache unavailable")
        return {"status": "ready"}

    return app
