"""Import en masse : coût en requêtes, idempotence, et transactionnalité par lot.

Comme le query service, un bulk writer **est** du SQL — ``ON CONFLICT``, ``INSERT``
multi-lignes, ``rowcount``. Le tester sans base ne prouverait rien : les tests
unitaires du use case (``tests/unit/application/test_import_tasks.py``) couvrent la
logique de tri et de rejet, ceux-ci couvrent ce que seule PostgreSQL peut dire.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_manager.application.task.dto import CreateTaskCommand, ImportTaskRow
from task_manager.application.task.use_cases.create_task import CreateTask
from task_manager.application.task.use_cases.import_tasks import ImportTasks
from task_manager.application.user.dto import UserDTO
from task_manager.domain.task.value_objects import TaskId
from task_manager.domain.user.value_objects import UserId
from task_manager.infrastructure.persistence.task.bulk import SqlAlchemyTaskBulkWriter
from task_manager.infrastructure.persistence.task.models import TaskModel
from task_manager.infrastructure.persistence.task.queries import SqlAlchemyTaskQueryService
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from task_manager.infrastructure.persistence.user.bulk import SqlAlchemyUserBulkWriter
from task_manager.infrastructure.persistence.user.models import UserModel
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository

from .test_exports_api import CompteurSQL

LIGNES = 50


class Compteur(CompteurSQL):
    """Ajoute le comptage des écritures à celui des lectures."""

    @property
    def inserts(self) -> int:
        return sum(1 for r in self.requetes if r.lstrip().upper().startswith("INSERT"))


@pytest.fixture
def compteur_ecritures(session_factory: async_sessionmaker[AsyncSession]):  # noqa: ANN201
    engine = session_factory.kw["bind"].sync_engine
    c = Compteur()
    event.listen(engine, "before_cursor_execute", c)
    yield c
    event.remove(engine, "before_cursor_execute", c)


def _lignes(nombre: int, *, owner_id: str, statut: str = "todo") -> list[ImportTaskRow]:
    """Fabrique un export plausible : plusieurs tâches, un seul propriétaire."""
    cree = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
    return [
        ImportTaskRow(
            task_id=str(TaskId.generate()),
            title=f"Tâche importée {i}",
            description=f"Description {i}",
            status=statut,
            created_at=cree.isoformat(),
            completed_at=cree.isoformat() if statut == "done" else None,
            owner_id=owner_id,
            owner_name="Ada Lovelace",
            owner_email="ada@example.com",
        )
        for i in range(nombre)
    ]


def _use_case(session: AsyncSession, *, batch_size: int = 1000) -> ImportTasks:
    return ImportTasks(
        tasks=SqlAlchemyTaskBulkWriter(session),
        users=SqlAlchemyUserBulkWriter(session),
        uow=SqlAlchemyUnitOfWork(session),
        batch_size=batch_size,
    )


async def test_importe_les_taches_et_leur_proprietaire(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un déploiement vierge : ni le user ni les tâches n'existent encore."""

    owner_id = str(UserId.generate())

    async with session_factory() as session:
        rapport = await _use_case(session).execute(_lignes(LIGNES, owner_id=owner_id))

    assert rapport.rows_read == LIGNES
    assert rapport.tasks.inserted == LIGNES
    assert rapport.users.inserted == 1
    assert rapport.rejected == 0

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(TaskModel)) == LIGNES
        assert await session.scalar(select(func.count()).select_from(UserModel)) == 1


async def test_conserve_les_identites_et_les_dates_de_lorigine(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ce que ``CreateTask`` aurait détruit : id, date de création, état terminé."""

    owner_id = str(UserId.generate())
    lignes = _lignes(1, owner_id=owner_id, statut="done")
    (ligne,) = lignes

    async with session_factory() as session:
        await _use_case(session).execute(lignes)

    async with session_factory() as session:
        task = await SqlAlchemyTaskRepository(session).get(TaskId.from_string(ligne.task_id))

    assert str(task.id) == ligne.task_id
    assert task.created_at.isoformat() == ligne.created_at
    assert task.status.value == "done"
    assert task.completed_at is not None


async def test_le_cout_en_requetes_ne_depend_pas_du_nombre_de_lignes(
    session_factory: async_sessionmaker[AsyncSession], compteur_ecritures: Compteur
) -> None:
    """Le geste central : deux ``INSERT`` par lot, quel que soit le volume.

    Le chemin unitaire en ferait trois par ligne (``exists`` + ``get`` + ``INSERT``) ;
    c'est ce que mesure le test suivant.
    """

    owner_id = str(UserId.generate())

    async with session_factory() as session:
        await _use_case(session).execute(_lignes(LIGNES, owner_id=owner_id))

    # Un INSERT users + un INSERT tasks. Rien de plus : pas de lecture préalable,
    # pas de vérification d'existence du propriétaire.
    assert compteur_ecritures.inserts == 2
    assert compteur_ecritures.selects == 0


async def test_le_chemin_unitaire_ferait_trois_requetes_par_ligne(
    session_factory: async_sessionmaker[AsyncSession],
    compteur_ecritures: Compteur,
    seeded_user: UserDTO,
) -> None:
    """Contre-mesure : le coût que l'import évite.

    Test inhabituel — il mesure un défaut — mais c'est ce qui empêche la
    démonstration de se périmer en silence le jour où ``CreateTask`` change.
    """

    compteur_ecritures.requetes.clear()

    async with session_factory() as session:
        use_case = CreateTask(SqlAlchemyTaskRepository(session), SqlAlchemyUserRepository(session))
        for i in range(LIGNES):
            await use_case.execute(CreateTaskCommand(owner_id=seeded_user.id, title=f"T{i}"))
        await session.commit()

    # ``exists`` puis ``session.get`` : deux SELECT par tâche.
    assert compteur_ecritures.selects == 2 * LIGNES
    assert compteur_ecritures.inserts >= LIGNES


async def test_rejouer_le_meme_fichier_est_sans_effet(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Idempotence prouvée contre PostgreSQL, pas contre une doublure."""

    lignes = _lignes(LIGNES, owner_id=str(UserId.generate()))

    async with session_factory() as session:
        premier = await _use_case(session).execute(lignes)
    async with session_factory() as session:
        second = await _use_case(session).execute(lignes)

    assert premier.tasks.inserted == LIGNES
    assert second.tasks.inserted == 0
    assert second.tasks.skipped == LIGNES
    assert second.users.inserted == 0

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(TaskModel)) == LIGNES


async def test_un_email_deja_pris_par_une_autre_identite_nemporte_pas_le_lot(
    session_factory: async_sessionmaker[AsyncSession], seeded_user: UserDTO
) -> None:
    """L'unicité de l'e-mail est une seconde contrainte, souvent oubliée.

    Sans ``ON CONFLICT`` sans cible, elle lèverait une ``IntegrityError`` et ferait
    échouer les 49 autres lignes.
    """

    homonyme = str(UserId.generate())
    lignes = [
        ImportTaskRow(
            task_id=ligne.task_id,
            title=ligne.title,
            description=ligne.description,
            status=ligne.status,
            created_at=ligne.created_at,
            completed_at=ligne.completed_at,
            owner_id=homonyme,
            owner_name="Homonyme",
            owner_email=seeded_user.email,
        )
        for ligne in _lignes(LIGNES, owner_id=str(UserId.generate()))
    ]

    async with session_factory() as session:
        rapport = await _use_case(session).execute(lignes)

    # L'utilisateur est ignoré (e-mail déjà pris)…
    assert rapport.users.inserted == 0
    assert rapport.users.skipped == 1
    # … et ses tâches sont rejetées plutôt que de faire exploser le lot : sans ce
    # filtre, l'INSERT entier partirait en ForeignKeyViolationError.
    assert rapport.tasks.inserted == 0
    assert rapport.rejected == LIGNES
    assert "e-mail déjà utilisé" in rapport.rejections[0].reason


async def test_les_lots_sont_commites_au_fil_de_leau(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """L'import n'est pas atomique, et c'est le comportement voulu.

    Une transaction unique de dix minutes épinglerait une connexion serveur derrière
    PgBouncer et perdrait tout sur un échec tardif. On échange l'atomicité globale
    contre la reprise — que l'idempotence rend sûre.
    """

    lignes = _lignes(30, owner_id=str(UserId.generate()))

    async with session_factory() as session:
        use_case = _use_case(session, batch_size=10)

        # On interrompt après le deuxième lot : les deux premiers sont déjà acquis.
        def flux():  # noqa: ANN202
            for index, ligne in enumerate(lignes):
                if index == 20:
                    raise RuntimeError("panne simulée")
                yield ligne

        with pytest.raises(RuntimeError):
            await use_case.execute(flux())

    async with session_factory() as session:
        restantes = await session.scalar(select(func.count()).select_from(TaskModel))

    assert restantes == 20


async def test_laller_retour_ne_perd_plus_la_description(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La description a été ajoutée au DTO d'export **pour** l'import.

    Aucun écran ne l'affiche : c'est le modèle de lecture qui porte désormais une
    colonne au service du chemin d'écriture. Le couplage export/import, décrit au
    chapitre 10, se voit ici dans le sens inverse de celui qu'on attend.
    """
    owner_id = str(UserId.generate())
    lignes = _lignes(3, owner_id=owner_id)

    async with session_factory() as session:
        await _use_case(session).execute(lignes)

    async with session_factory() as session:
        exportees = {
            item.task_id: item
            async for item in SqlAlchemyTaskQueryService(session).stream_with_owner()
        }

    for ligne in lignes:
        assert exportees[ligne.task_id].description == ligne.description
