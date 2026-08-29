"""Tests du mapping des exceptions → réponses HTTP (frontière présentation).

Application minimale montée à la main (aucune dépendance externe) : on vérifie
que ``register_error_handlers`` traduit correctement les familles d'exceptions,
en particulier les erreurs d'infrastructure → 503.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from task_manager.application.shared.errors import EmailSendError, InfrastructureError
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.presentation.api.error_handlers import register_error_handlers


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom/infra")
    async def _infra() -> None:
        raise EmailSendError("SMTP injoignable")

    @app.get("/boom/not-found")
    async def _not_found() -> None:
        raise UserNotFound("42")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_infrastructure_error_maps_to_503(client: AsyncClient) -> None:
    # ``EmailSendError`` hérite d'``InfrastructureError`` : le handler de la base
    # la couvre (FastAPI remonte la MRO).
    response = await client.get("/boom/infra")

    assert response.status_code == 503
    # Le détail technique n'est pas exposé au client.
    assert "SMTP" not in response.json()["detail"]


async def test_domain_not_found_still_maps_to_404(client: AsyncClient) -> None:
    # Régression : l'ajout du handler infra ne doit pas capter les erreurs métier.
    response = await client.get("/boom/not-found")

    assert response.status_code == 404


def test_infrastructure_error_is_not_a_domain_error() -> None:
    # Garde-fou : les deux hiérarchies restent disjointes, sinon le mapping
    # (400/404/409/422 vs 503) deviendrait ambigu.
    from task_manager.domain.shared.exceptions import DomainError

    assert not issubclass(InfrastructureError, DomainError)
    assert not issubclass(DomainError, InfrastructureError)
