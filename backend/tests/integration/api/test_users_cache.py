"""Tests d'intégration du cache de lecture des utilisateurs.

Le cache est un adaptateur : on l'exerce à travers l'API, en observant le vrai
Valkey (clé écrite, TTL, contenu) plutôt que la mécanique interne.
"""

from __future__ import annotations

import orjson
from httpx import AsyncClient
from redis.asyncio import Redis


async def _create_user(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/users", json={"name": "Ada Lovelace", "email": "ada@example.com"}
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_get_user_writes_the_entry_in_cache(client: AsyncClient, cache: Redis) -> None:
    user_id = await _create_user(client)
    # La création seule ne remplit pas le cache : seule la lecture le fait.
    assert await cache.get(f"user:{user_id}") is None

    await client.get(f"/api/v1/users/{user_id}")

    cached = await cache.get(f"user:{user_id}")
    assert cached is not None
    payload = orjson.loads(cached)
    assert payload["id"] == user_id
    assert payload["name"] == "Ada Lovelace"


async def test_cached_entry_expires(client: AsyncClient, cache: Redis) -> None:
    user_id = await _create_user(client)
    await client.get(f"/api/v1/users/{user_id}")

    # Une entrée sans TTL resterait indéfiniment : on vérifie qu'elle est bornée
    # (``ttl`` renvoie -1 pour une clé persistante, -2 si elle n'existe pas).
    ttl = await cache.ttl(f"user:{user_id}")
    assert 0 < ttl <= 300


async def test_second_read_is_served_from_cache(client: AsyncClient, cache: Redis) -> None:
    user_id = await _create_user(client)
    await client.get(f"/api/v1/users/{user_id}")

    # On altère l'entrée en cache : si la seconde lecture la renvoie, c'est
    # qu'elle vient bien du cache et non de la base.
    tampered = orjson.loads(await cache.get(f"user:{user_id}"))
    tampered["name"] = "Valeur venue du cache"
    await cache.set(f"user:{user_id}", orjson.dumps(tampered))

    response = await client.get(f"/api/v1/users/{user_id}")
    assert response.json()["name"] == "Valeur venue du cache"


async def test_cached_read_returns_the_same_payload(client: AsyncClient) -> None:
    # Le hit reconstruit un DTO depuis du JSON (où ``created_at`` est une
    # chaîne) : la réponse doit être identique à celle servie par la base.
    user_id = await _create_user(client)

    from_db = await client.get(f"/api/v1/users/{user_id}")
    from_cache = await client.get(f"/api/v1/users/{user_id}")

    assert from_cache.status_code == 200
    assert from_cache.json() == from_db.json()


async def test_unreadable_entry_falls_back_to_database(client: AsyncClient, cache: Redis) -> None:
    user_id = await _create_user(client)
    # Entrée corrompue (format changé, écriture partielle) : elle ne doit pas
    # faire échouer la requête, la base reste la source de vérité.
    await cache.set(f"user:{user_id}", "ceci n'est pas du json")

    response = await client.get(f"/api/v1/users/{user_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Ada Lovelace"


async def test_rename_invalidates_the_cache(client: AsyncClient, cache: Redis) -> None:
    user_id = await _create_user(client)
    # Première lecture : remplit le cache avec l'ancien nom.
    await client.get(f"/api/v1/users/{user_id}")
    assert await cache.get(f"user:{user_id}") is not None

    # La mutation doit invalider l'entrée…
    renamed = await client.patch(f"/api/v1/users/{user_id}", json={"name": "Grace Hopper"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Grace Hopper"
    assert await cache.get(f"user:{user_id}") is None

    # …et la lecture suivante repart de la base (nouveau nom, pas l'ancien caché).
    reread = await client.get(f"/api/v1/users/{user_id}")
    assert reread.json()["name"] == "Grace Hopper"


async def test_invalid_id_is_rejected_before_touching_the_cache(
    client: AsyncClient, cache: Redis
) -> None:
    response = await client.get("/api/v1/users/pas-un-uuid")

    assert response.status_code == 422
    assert await cache.keys("user:*") == []
