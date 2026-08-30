"""La course entre le contrôle applicatif et la contrainte d'unicité.

``CreateUser`` vérifie l'e-mail avant d'écrire, mais ce contrôle n'est pas
atomique : deux requêtes peuvent le passer avant qu'aucune n'ait committé. Ces
tests couvrent ce que la contrainte de base fait alors, et surtout **ce que
l'appelant en apprend**.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_manager.application.user.dto import CreateUserCommand
from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.domain.user.exceptions import EmailAlreadyUsed
from task_manager.domain.user.value_objects import Email
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository


async def test_deux_transactions_concurrentes_la_seconde_est_refusee_en_metier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Le cœur du sujet : la seconde écriture lève une erreur **métier**.

    Sans la traduction faite par le repository, ce serait une ``IntegrityError``
    SQLAlchemy — une erreur technique, qu'aucun gestionnaire ne sait convertir en
    statut HTTP.
    """
    commande = CreateUserCommand(name="Ada", email="course@example.com")

    async with session_factory() as premiere, session_factory() as seconde:
        r1 = SqlAlchemyUserRepository(premiere)
        r2 = SqlAlchemyUserRepository(seconde)
        # Les deux passent le contrôle applicatif : aucune ne voit l'autre.
        assert await r1.find_by_email(Email(commande.email)) is None
        assert await r2.find_by_email(Email(commande.email)) is None

        await CreateUser(r1).execute(commande)
        await premiere.commit()

        with pytest.raises(EmailAlreadyUsed):
            await CreateUser(r2).execute(commande)


async def test_le_client_recoit_409_et_non_un_faux_succes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Régression : la réponse ne doit plus mentir.

    Avant la traduction, l'``INSERT`` partait au ``commit``, donc après la
    construction de la réponse : le client recevait un ``201`` complet pour une
    transaction annulée. On simule ici la course en aveuglant le contrôle
    applicatif — la contrainte reste seule à trancher.
    """
    premier = await client.post(
        "/api/v1/users", json={"name": "Ada", "email": "doublon@example.com"}
    )
    assert premier.status_code == 201

    async def sans_rien_voir(self: SqlAlchemyUserRepository, email: Email) -> None:
        return None

    monkeypatch.setattr(SqlAlchemyUserRepository, "find_by_email", sans_rien_voir)

    second = await client.post(
        "/api/v1/users", json={"name": "Grace", "email": "doublon@example.com"}
    )

    assert second.status_code == 409
    assert "doublon@example.com" in second.json()["detail"]


async def test_requetes_simultanees_une_seule_passe(client: AsyncClient) -> None:
    """Bout en bout : peu importe qui gagne, il n'y a qu'un user et aucun 5xx."""
    reponses = await asyncio.gather(
        *(
            client.post("/api/v1/users", json={"name": f"U{i}", "email": "rafale@example.com"})
            for i in range(8)
        )
    )
    codes = sorted(r.status_code for r in reponses)

    assert codes.count(201) == 1
    assert set(codes) == {201, 409}
