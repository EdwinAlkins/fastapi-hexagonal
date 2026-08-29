"""Câblage port → adaptateur concret.

Cœur de la composition root : le seul endroit où les ports du domaine sont reliés
à leurs implémentations d'infrastructure. Transverse par nature (les use cases
inter-agrégats, comme ``CreateTask``, consomment plusieurs de ces adaptateurs).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.user.repository import UserRepository
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository
from task_manager.presentation.api.dependencies.session import SessionDep


def get_task_repository(session: SessionDep) -> TaskRepository:
    """Fournit l'implémentation concrète du port de persistance des tâches."""
    return SqlAlchemyTaskRepository(session)


def get_user_repository(session: SessionDep) -> UserRepository:
    """Fournit l'implémentation concrète du port de persistance des utilisateurs."""
    return SqlAlchemyUserRepository(session)


TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
