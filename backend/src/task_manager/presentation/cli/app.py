# presentation/cli/app.py
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import click
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.user.dto import CreateUserCommand
from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.infrastructure.config import get_settings
from task_manager.infrastructure.logging import configure_logging
from task_manager.infrastructure.persistence.database import create_engine, create_session_factory
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository


@asynccontextmanager
async def transactional_session() -> AsyncIterator[AsyncSession]:
    """Frontière transactionnelle du CLI, alignée sur ``get_session`` de l'API.

    Commit en sortie de bloc si succès, rollback sur toute exception ; le moteur
    est disposé en fin de commande (le CLI est un process court-lived).
    """
    settings = get_settings()
    engine = create_engine(settings.database_url, echo=settings.echo_sql)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


@click.group()
def cli() -> None:
    """CLI Task Manager."""
    configure_logging(get_settings().log_level)


@cli.command("create-user")
@click.option("--name", required=True, help="Nom de l'utilisateur")
@click.option("--email", required=True, help="Adresse e-mail de l'utilisateur")
def create_user(name: str, email: str) -> None:
    asyncio.run(_create_user(name, email))


async def _create_user(name: str, email: str) -> None:
    async with transactional_session() as session:
        use_case = CreateUser(repository=SqlAlchemyUserRepository(session))
        result = await use_case.execute(CreateUserCommand(name=name, email=email))

    click.echo(f"Utilisateur créé : {result.id}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
