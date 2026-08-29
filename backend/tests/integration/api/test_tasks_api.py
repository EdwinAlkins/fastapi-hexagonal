"""Tests d'intégration de l'API des tâches (parcours complet + cas d'erreur).

Une tâche appartient toujours à un utilisateur : chaque test part donc d'un
propriétaire déjà présent (fixture ``owner_id``, semée via le use case), puis
agit sur ses tâches sous la route imbriquée ``/users/{id}/tasks``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from task_manager.application.task.dto import TaskDTO
from task_manager.application.user.dto import UserDTO


@pytest.fixture
def owner_id(seeded_user: UserDTO) -> str:
    """Identifiant d'un propriétaire déjà présent (semé via le use case)."""
    return seeded_user.id


async def test_full_task_lifecycle(client: AsyncClient, owner_id: str) -> None:
    # Création (route imbriquée sous le propriétaire)
    created = await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "Rédiger la doc"})
    assert created.status_code == 201
    task = created.json()
    task_id = task["id"]
    assert task["status"] == "todo"
    assert task["completed_at"] is None
    assert task["owner_id"] == owner_id

    # Liste globale
    listed = await client.get("/api/v1/tasks")
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [task_id]

    # Récupération
    fetched = await client.get(f"/api/v1/tasks/{task_id}")
    assert fetched.status_code == 200

    # Complétion
    completed = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"
    assert completed.json()["completed_at"] is not None

    # Suppression
    deleted = await client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 204

    assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 404


async def test_create_task_for_unknown_user_returns_404(client: AsyncClient) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    response = await client.post(f"/api/v1/users/{unknown}/tasks", json={"title": "Orpheline"})
    assert response.status_code == 404


async def test_get_unknown_task_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_create_task_with_blank_title_is_rejected(client: AsyncClient, owner_id: str) -> None:
    # "   " passe min_length=1 mais est rejeté par le domaine (EmptyTitle) → 422.
    response = await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "   "})
    assert response.status_code == 422


async def test_complete_twice_returns_conflict(client: AsyncClient, owner_id: str) -> None:
    task_id = (
        await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "Tâche"})
    ).json()["id"]
    await client.post(f"/api/v1/tasks/{task_id}/complete")

    conflict = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert conflict.status_code == 409


async def test_start_task(client: AsyncClient, owner_id: str) -> None:
    task_id = (
        await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "Tâche"})
    ).json()["id"]

    started = await client.post(f"/api/v1/tasks/{task_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"


async def test_rename_task(client: AsyncClient, owner_id: str) -> None:
    task_id = (
        await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "Ancien"})
    ).json()["id"]

    renamed = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "Nouveau"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Nouveau"


async def test_malformed_uuid_returns_422(client: AsyncClient) -> None:
    # UUID invalide → erreur métier InvalidTaskId → 422 (et non 500).
    response = await client.get("/api/v1/tasks/not-a-uuid")
    assert response.status_code == 422


async def test_too_long_title_returns_422(client: AsyncClient, owner_id: str) -> None:
    response = await client.post(f"/api/v1/users/{owner_id}/tasks", json={"title": "x" * 201})
    assert response.status_code == 422


async def test_list_pagination(client: AsyncClient, seeded_tasks: list[TaskDTO]) -> None:
    # ``seeded_tasks`` en pose trois d'avance (semées via le use case) : la
    # pagination est le seul comportement sous test, pas leur création.
    page = await client.get("/api/v1/tasks", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    assert len(page.json()) == 2


async def test_liveness_returns_ok(client: AsyncClient) -> None:
    # ``/health`` est un simple liveness : il ne vérifie aucune dépendance.
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_dependencies(client: AsyncClient) -> None:
    # ``/ready`` vérifie les dépendances critiques pour servir une requête (DB et
    # cache) : c'est lui, et non ``/health``, qui touche la base.
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
