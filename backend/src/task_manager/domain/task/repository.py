"""Port de persistance des tâches (interface, côté « driven »).

Le domaine définit *ce dont il a besoin* ; l'infrastructure fournira une
implémentation concrète. Aucune dépendance technique ici.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from task_manager.domain.task.entities import Task
from task_manager.domain.task.value_objects import TaskId
from task_manager.domain.user.value_objects import UserId


class TaskRepository(ABC):
    """Contrat de persistance de l'agrégat :class:`Task`."""

    @abstractmethod
    async def save(self, task: Task) -> None:
        """Persiste l'état de l'agrégat, qu'il soit nouveau ou modifié."""

    @abstractmethod
    async def get(self, task_id: TaskId) -> Task:
        """Récupère une tâche. Lève ``TaskNotFound`` si absente."""

    # Déclarée avant ``list`` : une annotation ``list[Task]`` placée après la
    # méthode ``list`` la résoudrait vers cette méthode (shadowing du builtin).
    @abstractmethod
    async def list_by_owner(
        self, owner_id: UserId, *, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        """Retourne les tâches d'un utilisateur donné (côté « n » de la relation)."""

    @abstractmethod
    async def list(self, *, limit: int = 100, offset: int = 0) -> list[Task]:
        """Retourne les tâches, avec pagination (bornée)."""

    @abstractmethod
    async def delete(self, task_id: TaskId) -> None:
        """Supprime une tâche. Lève ``TaskNotFound`` si absente."""

    @abstractmethod
    async def exists(self, task_id: TaskId) -> bool:
        """Vérifie si une tâche existe. Retourne ``True`` si elle existe, ``False`` sinon."""
