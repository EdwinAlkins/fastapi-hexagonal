"""Tests unitaires du use case ``GetUser`` (cache-aside : hit / miss)."""

from __future__ import annotations

from dataclasses import asdict

from task_manager.application.user.dto import UserDTO
from task_manager.application.user.use_cases.get_user import GetUser
from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserName
from tests.unit.application._fakes import FakeCache, FakeUserRepository


def _a_user() -> User:
    return User.create(name=UserName("Ada"), email=Email("ada@example.com"))


class TestGetUser:
    async def test_cache_miss_loads_repo_and_fills_cache(self) -> None:
        user = _a_user()
        repo = FakeUserRepository([user])
        cache = FakeCache()
        use_case = GetUser(repository=repo, cache=cache)

        dto = await use_case.execute(str(user.id))

        assert dto.id == str(user.id)
        assert repo.get_calls == 1
        # Le miss remplit le cache pour les prochaines lectures.
        assert cache.sets == [(f"user:{user.id}", asdict(dto))]

    async def test_cache_hit_skips_repo(self) -> None:
        user = _a_user()
        dto = UserDTO.from_entity(user)
        cache = FakeCache({f"user:{user.id}": asdict(dto)})
        # Repo vide : s'il était interrogé, ``get`` lèverait ``UserNotFound``.
        repo = FakeUserRepository([])
        use_case = GetUser(repository=repo, cache=cache)

        result = await use_case.execute(str(user.id))

        assert result.id == str(user.id)
        assert result.name == "Ada"
        assert repo.get_calls == 0
