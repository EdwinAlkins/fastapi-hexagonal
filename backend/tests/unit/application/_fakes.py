"""Doublures en mémoire des ports, pour tester les use cases sans I/O.

Les use cases ne dépendent que des ports (repositories, cache, SMTP, publisher) :
on les substitue ici par des implémentations triviales en mémoire, ce qui permet
de couvrir les branches (cache hit/miss, entité absente, échec d'envoi…) sans
base de données ni broker.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.application.shared.cache import CachePort
from task_manager.application.shared.errors import EmailSendError
from task_manager.application.shared.html_template.email_template import EmailTemplatePort
from task_manager.application.shared.messaging import EventPublisherPort, IntegrationEvent
from task_manager.application.shared.smtp import SMTPSenderPort
from task_manager.application.shared.unit_of_work import UnitOfWorkPort
from task_manager.application.task.bulk import TaskBulkWriterPort
from task_manager.application.user.bulk import UserBulkWriterPort
from task_manager.domain.task.entities import Task
from task_manager.domain.task.exceptions import TaskNotFound
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId
from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import UserNotFound
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import Email, UserId


class FakeUserRepository(UserRepository):
    """Repository utilisateur en mémoire."""

    def __init__(self, users: list[User] | None = None) -> None:
        self._by_id: dict[UserId, User] = {u.id: u for u in (users or [])}
        self.get_calls = 0

    async def save(self, user: User) -> None:
        self._by_id[user.id] = user

    async def get(self, user_id: UserId) -> User:
        self.get_calls += 1
        try:
            return self._by_id[user_id]
        except KeyError:
            raise UserNotFound(str(user_id)) from None

    async def exists(self, user_id: UserId) -> bool:
        return user_id in self._by_id

    async def find_by_email(self, email: Email) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return list(self._by_id.values())[offset : offset + limit]


class FakeTaskRepository(TaskRepository):
    """Repository tâche en mémoire."""

    def __init__(self, tasks: list[Task] | None = None) -> None:
        self._by_id: dict[TaskId, Task] = {t.id: t for t in (tasks or [])}
        self.saved: list[Task] = []

    async def save(self, task: Task) -> None:
        self._by_id[task.id] = task
        self.saved.append(task)

    async def get(self, task_id: TaskId) -> Task:
        try:
            return self._by_id[task_id]
        except KeyError:
            raise TaskNotFound(str(task_id)) from None

    async def list_by_owner(
        self, owner_id: UserId, *, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        owned = [t for t in self._by_id.values() if t.owner_id == owner_id]
        return owned[offset : offset + limit]

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[Task]:
        return list(self._by_id.values())[offset : offset + limit]

    async def delete(self, task_id: TaskId) -> None:
        if self._by_id.pop(task_id, None) is None:
            raise TaskNotFound(str(task_id))

    async def exists(self, task_id: TaskId) -> bool:
        return task_id in self._by_id


class FakeCache(CachePort):
    """Cache en mémoire, qui enregistre les écritures pour les assertions."""

    def __init__(self, store: dict[str, dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = dict(store or {})
        self.sets: list[tuple[str, dict[str, Any]]] = []
        self.deletes: list[str] = []

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        self._store[key] = value
        self.sets.append((key, value))

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self.deletes.append(key)

    async def ping(self) -> bool:
        return True


class RecordingPublisher(EventPublisherPort):
    """Publisher qui mémorise les événements publiés."""

    def __init__(self) -> None:
        self.published: list[IntegrationEvent] = []

    async def publish(self, event: IntegrationEvent) -> None:
        self.published.append(event)


class FakeTemplate(EmailTemplatePort):
    """Rendu de template inerte."""

    def render_share_task(self, **kwargs: str) -> str:
        return "<html>rendu</html>"


class FakeSMTP(SMTPSenderPort):
    """Envoi SMTP en mémoire ; échoue pour les adresses de ``fail_for``."""

    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.fail_for = fail_for or set()
        self.sent: list[dict[str, str]] = []

    async def send(self, to_email: str, subject: str, body: str, from_email: str) -> None:
        if to_email in self.fail_for:
            raise EmailSendError(f"échec simulé pour {to_email}")
        self.sent.append({"to": to_email, "subject": subject, "body": body, "from": from_email})


class FakeUserBulkWriter(UserBulkWriterPort):
    """Écriture groupée d'utilisateurs, en mémoire.

    Reproduit le point qui compte pour les tests : la sémantique ``ON CONFLICT DO
    NOTHING``. Une identité déjà connue est *ignorée*, jamais écrasée ni remontée
    en erreur. ``batches`` conserve la taille de chaque lot reçu, ce qui permet de
    vérifier que le use case groupe réellement ses écritures.
    """

    def __init__(self, existing: list[User] | None = None) -> None:
        self.stored: dict[UserId, User] = {u.id: u for u in (existing or [])}
        self.batches: list[int] = []
        self.existence_queries = 0

    async def existing_ids(self, user_ids: Sequence[UserId]) -> set[UserId]:
        self.existence_queries += 1
        return {uid for uid in user_ids if uid in self.stored}

    async def save_all(self, users: Sequence[User]) -> BulkWriteResult:
        self.batches.append(len(users))
        inserted = 0
        for user in users:
            if user.id in self.stored:
                continue
            self.stored[user.id] = user
            inserted += 1
        return BulkWriteResult(inserted=inserted, skipped=len(users) - inserted)


class FakeTaskBulkWriter(TaskBulkWriterPort):
    """Écriture groupée de tâches, en mémoire (même sémantique que ci-dessus)."""

    def __init__(self, existing: list[Task] | None = None) -> None:
        self.stored: dict[TaskId, Task] = {t.id: t for t in (existing or [])}
        self.batches: list[int] = []

    async def save_all(self, tasks: Sequence[Task]) -> BulkWriteResult:
        self.batches.append(len(tasks))
        inserted = 0
        for task in tasks:
            if task.id in self.stored:
                continue
            self.stored[task.id] = task
            inserted += 1
        return BulkWriteResult(inserted=inserted, skipped=len(tasks) - inserted)


class FakeUnitOfWork(UnitOfWorkPort):
    """Compte les commits, seule chose qu'un test ait besoin d'observer ici."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1
