"""Tests unitaires du use case ``CreateTask`` (orchestration inter-agrégats)."""

from __future__ import annotations

import pytest

from task_manager.application.task.dto import CreateTaskCommand
from task_manager.application.task.use_cases.create_task import CreateTask
from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.value_objects import Email, UserName
from tests.unit.application._fakes import FakeTaskRepository, FakeUserRepository


def _a_user() -> User:
    return User.create(name=UserName("Ada"), email=Email("ada@example.com"))


class TestCreateTask:
    async def test_creates_task_when_owner_exists(self) -> None:
        owner = _a_user()
        tasks = FakeTaskRepository()
        use_case = CreateTask(tasks=tasks, users=FakeUserRepository([owner]))

        dto = await use_case.execute(
            CreateTaskCommand(owner_id=str(owner.id), title="Écrire les tests")
        )

        assert dto.owner_id == str(owner.id)
        assert dto.title == "Écrire les tests"
        assert dto.status == "todo"
        # La tâche a bien été persistée via le port.
        assert len(tasks.saved) == 1

    async def test_raises_when_owner_missing(self) -> None:
        # Vérification de cohérence référentielle côté application : pas de tâche
        # créée pour un propriétaire inexistant.
        tasks = FakeTaskRepository()
        use_case = CreateTask(tasks=tasks, users=FakeUserRepository([]))

        missing_owner = _a_user()
        with pytest.raises(UserNotFound):
            await use_case.execute(CreateTaskCommand(owner_id=str(missing_owner.id), title="X"))
        assert tasks.saved == []
