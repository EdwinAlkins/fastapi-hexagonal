"""La course entre le contrôle applicatif et la clé étrangère.

Pendant symétrique de ``test_unicite_email`` : ``CreateTask`` vérifie l'existence
du propriétaire avant d'écrire, mais ce contrôle n'est pas plus atomique que
celui de l'e-mail. Entre sa lecture et l'``INSERT``, l'utilisateur peut être
supprimé — et ``tasks.owner_id`` déclare ``ondelete=CASCADE``, donc rien ne
retient cette suppression. Ces tests couvrent ce que ``tasks_owner_id_fkey`` fait
alors, et surtout **ce que l'appelant en apprend**.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_manager.application.user.dto import UserDTO
from task_manager.domain.task.entities import Task
from task_manager.domain.task.value_objects import TaskTitle
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.value_objects import UserId
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository


async def test_ecrire_pour_un_proprietaire_absent_leve_une_erreur_metier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Le cœur du sujet : l'écriture lève une erreur **métier**.

    Sans la traduction faite par le repository, ce serait une ``IntegrityError``
    SQLAlchemy — une erreur technique, qu'aucun gestionnaire ne sait convertir en
    statut HTTP.
    """
    fantome = UserId.generate()
    task = Task.create(owner_id=fantome, title=TaskTitle("Orpheline"))

    async with session_factory() as session:
        with pytest.raises(UserNotFound):
            await SqlAlchemyTaskRepository(session).save(task)


async def test_le_client_recoit_404_et_non_un_faux_succes(
    client: AsyncClient, seeded_user: UserDTO, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Régression : la réponse ne doit pas mentir.

    Sans le ``flush``, l'``INSERT`` partirait au ``commit``, donc après la
    construction de la réponse : le client recevrait un ``201`` complet avec
    l'identifiant de la tâche, pour une transaction annulée. On simule ici la
    course en aveuglant le contrôle applicatif — la clé étrangère reste seule à
    trancher.
    """

    async def sans_rien_voir(self: SqlAlchemyUserRepository, user_id: UserId) -> bool:
        return True

    monkeypatch.setattr(SqlAlchemyUserRepository, "exists", sans_rien_voir)

    fantome = UserId.generate()
    reponse = await client.post(f"/api/v1/users/{fantome}/tasks", json={"title": "Orpheline"})

    assert reponse.status_code == 404
    assert str(fantome) in reponse.json()["detail"]

    # Et la tâche n'existe nulle part : le refus a bien annulé l'écriture.
    listees = await client.get("/api/v1/tasks")
    assert all(t["title"] != "Orpheline" for t in listees.json())
