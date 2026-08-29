"""Tests unitaires du use case ``NotifyTaskShared`` (agrégation des échecs SMTP)."""

from __future__ import annotations

from task_manager.application.task.dto import ShareTaskNotification
from task_manager.application.task.use_cases.notify_task_shared import NotifyTaskShared
from task_manager.domain.task.entities import Task
from task_manager.domain.task.value_objects import TaskTitle
from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserName
from tests.unit.application._fakes import (
    FakeSMTP,
    FakeTaskRepository,
    FakeTemplate,
    FakeUserRepository,
)


def _a_user(name: str, email: str) -> User:
    return User.create(name=UserName(name), email=Email(email))


class TestNotifyTaskShared:
    async def test_collects_unreachable_recipients(self) -> None:
        owner = _a_user("Owner", "owner@example.com")
        reachable = _a_user("Grace", "grace@example.com")
        unreachable = _a_user("Ada", "ada@example.com")
        task = Task.create(owner_id=owner.id, title=TaskTitle("Partagée"))

        smtp = FakeSMTP(fail_for={str(unreachable.email)})
        use_case = NotifyTaskShared(
            task_repository=FakeTaskRepository([task]),
            user_repository=FakeUserRepository([owner, reachable, unreachable]),
            smtp_sender=smtp,
            email_template=FakeTemplate(),
            from_email="noreply@example.com",
        )

        result = await use_case.execute(
            ShareTaskNotification(
                task_id=str(task.id),
                user_ids=[str(reachable.id), str(unreachable.id)],
                subject="Partage",
                body="Corps",
            )
        )

        # Seul le destinataire injoignable est remonté ; l'autre a bien reçu l'e-mail.
        assert result.failed == [str(unreachable.id)]
        assert [sent["to"] for sent in smtp.sent] == [str(reachable.email)]

    async def test_all_reachable_yields_no_failures(self) -> None:
        owner = _a_user("Owner", "owner@example.com")
        recipient = _a_user("Grace", "grace@example.com")
        task = Task.create(owner_id=owner.id, title=TaskTitle("Partagée"))

        use_case = NotifyTaskShared(
            task_repository=FakeTaskRepository([task]),
            user_repository=FakeUserRepository([owner, recipient]),
            smtp_sender=FakeSMTP(),
            email_template=FakeTemplate(),
            from_email="noreply@example.com",
        )

        result = await use_case.execute(
            ShareTaskNotification(
                task_id=str(task.id),
                user_ids=[str(recipient.id)],
                subject="Partage",
                body="Corps",
            )
        )

        assert result.failed == []
