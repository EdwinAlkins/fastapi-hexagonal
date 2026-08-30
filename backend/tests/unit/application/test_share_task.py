"""Tests unitaires du use case ``ShareTask`` (publication d'un message)."""

from __future__ import annotations

import pytest

from task_manager.application.task.dto import ShareTaskNotification
from task_manager.application.task.use_cases.share_task import ShareTask
from task_manager.domain.task.entities import Task
from task_manager.domain.task.exceptions import TaskNotFound
from task_manager.domain.task.value_objects import TaskTitle
from task_manager.domain.user.value_objects import UserId
from tests.unit.application._fakes import FakeTaskRepository, RecordingPublisher


def _a_task() -> Task:
    return Task.create(owner_id=UserId.generate(), title=TaskTitle("Partager"))


class TestShareTask:
    async def test_publishes_when_task_exists(self) -> None:
        task = _a_task()
        publisher = RecordingPublisher()
        use_case = ShareTask(task_repository=FakeTaskRepository([task]), message_adapter=publisher)

        await use_case.execute(
            task_id=str(task.id),
            user_ids=["u1", "u2"],
            subject="Sujet",
            body="Corps",
        )

        assert publisher.published == [
            ShareTaskNotification(
                task_id=str(task.id),
                user_ids=["u1", "u2"],
                subject="Sujet",
                body="Corps",
            )
        ]
        # Le type d'événement est porté par la classe, pas par le site d'appel.
        assert ShareTaskNotification.name == "task.shared"

    async def test_raises_and_publishes_nothing_when_task_missing(self) -> None:
        publisher = RecordingPublisher()
        use_case = ShareTask(task_repository=FakeTaskRepository([]), message_adapter=publisher)

        missing = _a_task()
        with pytest.raises(TaskNotFound):
            await use_case.execute(task_id=str(missing.id), user_ids=["u1"], subject="S", body="B")
        assert publisher.published == []
