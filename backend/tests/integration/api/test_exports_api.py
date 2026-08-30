"""Tests du chemin de lecture (query service) et de l'export NDJSON.

Un query service **est** du SQL : le tester sans base ne prouverait rien. Il n'y a
donc aucun test unitaire ici — le chemin de lecture inverse la pyramide, parce
qu'il n'a aucune logique pure à vérifier.
"""

from __future__ import annotations

import orjson
import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_manager.application.task.dto import TaskDTO
from task_manager.application.user.dto import UserDTO
from task_manager.infrastructure.persistence.task.queries import SqlAlchemyTaskQueryService
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository


class CompteurSQL:
    """Compte les requêtes réellement envoyées au moteur.

    C'est la seule façon honnête de prouver l'absence de N+1 : le nombre de
    requêtes est une propriété observable, pas une intention.
    """

    def __init__(self) -> None:
        self.requetes: list[str] = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        self.requetes.append(statement)

    @property
    def selects(self) -> int:
        return sum(1 for r in self.requetes if r.lstrip().upper().startswith("SELECT"))


@pytest.fixture
def compteur(session_factory: async_sessionmaker[AsyncSession]):  # noqa: ANN201
    """Branche un compteur sur le moteur de la session de test."""
    engine = session_factory.kw["bind"].sync_engine
    c = CompteurSQL()
    event.listen(engine, "before_cursor_execute", c)
    yield c
    event.remove(engine, "before_cursor_execute", c)


async def test_export_renvoie_une_ligne_ndjson_par_tache(
    client: AsyncClient, seeded_tasks: list[TaskDTO], seeded_user: UserDTO
) -> None:
    reponse = await client.get("/api/v1/exports/tasks")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in reponse.headers["content-disposition"]

    lignes = [orjson.loads(ligne) for ligne in reponse.content.splitlines() if ligne]
    assert len(lignes) == len(seeded_tasks)

    # La jointure est bien faite : chaque ligne porte le propriétaire, à plat.
    for ligne in lignes:
        assert ligne["owner_id"] == seeded_user.id
        assert ligne["owner_name"] == "Ada Lovelace"
        assert ligne["owner_email"] == "ada@example.com"
        assert set(ligne) == {
            "task_id",
            "title",
            "description",
            "status",
            "created_at",
            "completed_at",
            "owner_id",
            "owner_name",
            "owner_email",
        }


async def test_export_vide_ne_renvoie_aucune_ligne(client: AsyncClient) -> None:
    reponse = await client.get("/api/v1/exports/tasks")
    assert reponse.status_code == 200
    assert reponse.content == b""


async def test_le_compte_correspond_a_lexport(
    client: AsyncClient, seeded_tasks: list[TaskDTO]
) -> None:
    compte = await client.get("/api/v1/exports/tasks/count")
    assert compte.status_code == 200
    assert compte.json() == {"count": len(seeded_tasks)}


async def test_le_query_service_ne_fait_quune_requete(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_tasks: list[TaskDTO],
    compteur: CompteurSQL,
) -> None:
    """La preuve chiffrée : une requête, quel que soit le nombre de tâches."""
    async with session_factory() as session:
        service = SqlAlchemyTaskQueryService(session)
        lignes = [item async for item in service.stream_with_owner()]

    assert len(lignes) == len(seeded_tasks)
    assert compteur.selects == 1, f"attendu 1 SELECT, obtenu {compteur.selects}"


async def test_le_chemin_par_agregats_fait_n_plus_1(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_tasks: list[TaskDTO],
    compteur: CompteurSQL,
) -> None:
    """Le contre-exemple : reconstruire la même vue via les agrégats coûte N+1.

    Ce test n'existe pas pour valider un comportement souhaitable — il existe pour
    **mesurer** ce que le query service évite.
    """
    async with session_factory() as session:
        taches = SqlAlchemyTaskRepository(session)
        users = SqlAlchemyUserRepository(session)
        for task in await taches.list(limit=100):
            await users.get(task.owner_id)  # une requête par tâche

    attendu = 1 + len(seeded_tasks)
    assert compteur.selects == attendu, f"attendu {attendu} SELECT, obtenu {compteur.selects}"
