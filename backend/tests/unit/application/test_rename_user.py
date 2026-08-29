"""Tests unitaires du use case ``RenameUser`` (mutation + invalidation du cache)."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from task_manager.application.user.dto import UserDTO
from task_manager.application.user.use_cases.rename_user import RenameUser
from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.value_objects import Email, UserName
from tests.unit.application._fakes import FakeCache, FakeUserRepository


def _a_user() -> User:
    return User.create(name=UserName("Ada"), email=Email("ada@example.com"))


class TestRenameUser:
    async def test_renames_and_invalidates_cache(self) -> None:
        user = _a_user()
        # Le cache contient l'ancienne valeur avant la mutation.
        cache = FakeCache({f"user:{user.id}": asdict(UserDTO.from_entity(user))})
        use_case = RenameUser(repository=FakeUserRepository([user]), cache=cache)

        dto = await use_case.execute(str(user.id), "Grace")

        assert dto.name == "Grace"
        # L'entrée de cache a été invalidée (clé exacte), pas seulement écrasée.
        assert cache.deletes == [f"user:{user.id}"]
        assert await cache.get(f"user:{user.id}") is None

    async def test_raises_when_user_missing(self) -> None:
        cache = FakeCache()
        use_case = RenameUser(repository=FakeUserRepository([]), cache=cache)

        missing = _a_user()
        with pytest.raises(UserNotFound):
            await use_case.execute(str(missing.id), "Grace")
        # Pas de mutation → pas d'invalidation.
        assert cache.deletes == []
