"""Doublures en mémoire des ports, pour tester les use cases sans I/O.

Les use cases ne dépendent que des ports (repositories, cache, SMTP, publisher) :
on les substitue ici par des implémentations triviales en mémoire, ce qui permet
de couvrir les branches (cache hit/miss, entité absente, échec d'envoi…) sans
base de données ni broker.
"""

from __future__ import annotations

from typing import Any

from task_manager.application.shared.cache import CachePort
from task_manager.application.shared.errors import EmailSendError
from task_manager.application.shared.html_template.email_template import EmailTemplatePort
from task_manager.application.shared.messaging import EventPublisherPort
from task_manager.application.shared.smtp import SMTPSenderPort
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
    """Publisher qui mémorise les messages publiés."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        self.published.append((routing_key, payload))


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
