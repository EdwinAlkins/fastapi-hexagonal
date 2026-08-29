"""Tests d'intégration de l'API des utilisateurs et de la relation 1→n."""

from __future__ import annotations

from httpx import AsyncClient


async def _create_user(client: AsyncClient, *, email: str = "ada@example.com") -> str:
    response = await client.post("/api/v1/users", json={"name": "Ada Lovelace", "email": email})
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_create_and_get_user(client: AsyncClient) -> None:
    user_id = await _create_user(client)

    fetched = await client.get(f"/api/v1/users/{user_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"


async def test_email_must_be_unique(client: AsyncClient) -> None:
    await _create_user(client, email="dup@example.com")

    conflict = await client.post(
        "/api/v1/users", json={"name": "Autre", "email": "dup@example.com"}
    )
    assert conflict.status_code == 409


async def test_invalid_email_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/users", json={"name": "Ada", "email": "not-an-email"})
    assert response.status_code == 422


async def test_get_unknown_user_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_list_user_tasks_returns_only_owned_tasks(client: AsyncClient) -> None:
    alice = await _create_user(client, email="alice@example.com")
    bob = await _create_user(client, email="bob@example.com")

    await client.post(f"/api/v1/users/{alice}/tasks", json={"title": "Tâche d'Alice 1"})
    await client.post(f"/api/v1/users/{alice}/tasks", json={"title": "Tâche d'Alice 2"})
    await client.post(f"/api/v1/users/{bob}/tasks", json={"title": "Tâche de Bob"})

    alice_tasks = await client.get(f"/api/v1/users/{alice}/tasks")
    assert alice_tasks.status_code == 200
    titles = {t["title"] for t in alice_tasks.json()}
    assert titles == {"Tâche d'Alice 1", "Tâche d'Alice 2"}
    assert all(t["owner_id"] == alice for t in alice_tasks.json())

    bob_tasks = await client.get(f"/api/v1/users/{bob}/tasks")
    assert [t["title"] for t in bob_tasks.json()] == ["Tâche de Bob"]


async def test_list_tasks_of_unknown_user_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000/tasks")
    assert response.status_code == 404


async def test_list_tasks_of_user_without_tasks_is_empty(client: AsyncClient) -> None:
    user_id = await _create_user(client)

    response = await client.get(f"/api/v1/users/{user_id}/tasks")
    assert response.status_code == 200
    assert response.json() == []
