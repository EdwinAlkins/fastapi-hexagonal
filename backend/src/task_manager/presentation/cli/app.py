# presentation/cli/app.py
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import click
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from task_manager.application.task.dto import ImportReport, ImportTaskRow
from task_manager.application.task.use_cases.import_tasks import (
    DEFAULT_BATCH_SIZE,
    ImportTasks,
)
from task_manager.application.user.dto import CreateUserCommand
from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.infrastructure.config import get_settings
from task_manager.infrastructure.logging import configure_logging
from task_manager.infrastructure.persistence.database import create_engine, create_session_factory
from task_manager.infrastructure.persistence.task.bulk import SqlAlchemyTaskBulkWriter
from task_manager.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from task_manager.infrastructure.persistence.user.bulk import SqlAlchemyUserBulkWriter
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


@cli.command("import-tasks")
@click.argument(
    "fichier", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)
)
@click.option(
    "--batch-size",
    default=DEFAULT_BATCH_SIZE,
    show_default=True,
    help="Nombre de lignes par transaction.",
)
def import_tasks(fichier: Path, batch_size: int) -> None:
    """Importe un export de tâches : NDJSON, ou tableau JSON.

    Commande CLI et non route HTTP, délibérément : un import tient des minutes,
    là où une requête HTTP doit rendre la main. C'est l'illustration directe du
    principe du dépôt — la transaction entoure **le use case**, pas la requête.
    """
    asyncio.run(_import_tasks(fichier, batch_size))


def _en_ligne(brut: object) -> ImportTaskRow:
    """Objet JSON décodé → ligne typée.

    Lève ``KeyError`` ou ``TypeError`` si la forme ne convient pas ; l'appelant
    en fait une ligne illisible plutôt qu'un échec global.
    """
    if not isinstance(brut, dict):
        raise TypeError("objet JSON attendu")
    return ImportTaskRow(
        task_id=str(brut["task_id"]),
        title=str(brut["title"]),
        description=(str(brut["description"]) if brut.get("description") is not None else None),
        status=str(brut["status"]),
        created_at=str(brut["created_at"]),
        completed_at=str(brut["completed_at"]) if brut.get("completed_at") is not None else None,
        owner_id=str(brut["owner_id"]),
        owner_name=str(brut["owner_name"]),
        owner_email=str(brut["owner_email"]),
    )


def _lire(fichier: Path, illisibles: list[int]) -> Iterator[ImportTaskRow]:
    """Fichier d'export → flux de lignes typées.

    Deux formats sont acceptés, parce que ce dépôt en produit deux :

    - **NDJSON**, un objet par ligne, tel que le sert ``GET /api/v1/exports/tasks`` ;
    - **tableau JSON**, tel que l'enregistre le bouton « Exporter » du frontend,
      qui recompose un document lisible après avoir consommé le flux.

    C'est un rattrapage, pas une élégance : le format d'échange n'est défini nulle
    part ailleurs que dans le code qui l'écrit (cf. chapitre 10 du cours). Accepter
    les deux évite au moins qu'un fichier produit par ce dépôt lui soit inimportable.

    Le NDJSON est lu **paresseusement** — mémoire constante quel que soit le volume.
    Un tableau JSON, lui, doit être décodé en entier avant d'être parcouru : c'est
    la limite du format, pas de la lecture.
    """
    debut = fichier.read_bytes()[:64].lstrip()
    lecteur = _lire_tableau if debut.startswith(b"[") else _lire_ndjson
    yield from lecteur(fichier, illisibles)


def _lire_tableau(fichier: Path, illisibles: list[int]) -> Iterator[ImportTaskRow]:
    try:
        elements = orjson.loads(fichier.read_bytes())
    except orjson.JSONDecodeError as exc:
        raise click.ClickException(f"JSON illisible : {exc}") from exc
    if not isinstance(elements, list):
        raise click.ClickException("Attendu : un tableau JSON, ou des lignes NDJSON.")
    for rang, brut in enumerate(elements, start=1):
        try:
            yield _en_ligne(brut)
        except (KeyError, TypeError):
            illisibles.append(rang)


def _lire_ndjson(fichier: Path, illisibles: list[int]) -> Iterator[ImportTaskRow]:
    with fichier.open("rb") as flux:
        for numero, ligne in enumerate(flux, start=1):
            if not ligne.strip():
                continue
            try:
                yield _en_ligne(orjson.loads(ligne))
            except (orjson.JSONDecodeError, KeyError, TypeError):
                illisibles.append(numero)


async def _import_tasks(fichier: Path, batch_size: int) -> None:
    illisibles: list[int] = []
    async with transactional_session() as session:
        use_case = ImportTasks(
            tasks=SqlAlchemyTaskBulkWriter(session),
            users=SqlAlchemyUserBulkWriter(session),
            uow=SqlAlchemyUnitOfWork(session),
            batch_size=batch_size,
        )
        rapport = await use_case.execute(_lire(fichier, illisibles))

    _afficher(rapport, illisibles)


def _afficher(rapport: ImportReport, illisibles: list[int]) -> None:
    click.echo(f"Lignes lues        : {rapport.rows_read}")
    click.echo(
        f"Utilisateurs       : {rapport.users.inserted} créés, "
        f"{rapport.users.skipped} déjà présents"
    )
    click.echo(
        f"Tâches             : {rapport.tasks.inserted} importées, "
        f"{rapport.tasks.skipped} déjà présentes"
    )
    click.echo(f"Lignes rejetées    : {rapport.rejected}")

    for rejet in rapport.rejections[:20]:
        click.echo(f"  rang {rejet.line} ({rejet.task_id or '?'}) : {rejet.reason}")
    if rapport.rejected > 20:
        click.echo(f"  … et {rapport.rejected - 20} autres")

    if illisibles:
        # Numérotation distincte : le rang d'un rejet est sa position dans le flux
        # transmis au use case, qui ne contient pas les lignes écartées ici.
        click.echo(f"Lignes illisibles  : {len(illisibles)} (lignes {illisibles[:20]})")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
