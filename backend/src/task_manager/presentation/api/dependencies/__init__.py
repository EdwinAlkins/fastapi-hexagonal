"""Composition root de l'hexagone (façade).

Reste **le point d'entrée unique** du câblage DI : routers, application et tests
importent depuis ``...api.dependencies``. Le détail est réparti par
préoccupation transverse (``session``, ``repositories``) et par bounded context
(``task``, ``user``), mais ce module en réexpose la vue d'ensemble — on garde le
bénéfice d'une composition root centralisée sans le fourre-tout d'un fichier unique.
"""

from __future__ import annotations

from task_manager.presentation.api.dependencies.cache import CachePortDep
from task_manager.presentation.api.dependencies.repositories import (
    TaskRepositoryDep,
    UserRepositoryDep,
    get_task_repository,
    get_user_repository,
)
from task_manager.presentation.api.dependencies.session import SessionDep, get_session
from task_manager.presentation.api.dependencies.task import (
    TaskQueryDep,
    get_complete_task,
    get_create_task,
    get_delete_task,
    get_get_task,
    get_list_tasks,
    get_list_tasks_by_owner,
    get_rename_task,
    get_share_task,
    get_start_task,
)
from task_manager.presentation.api.dependencies.user import (
    get_create_user,
    get_get_user,
    get_list_users,
    get_rename_user,
)

__all__ = [
    # Transverse
    "SessionDep",
    "get_session",
    "TaskRepositoryDep",
    "UserRepositoryDep",
    "get_task_repository",
    "get_user_repository",
    "CachePortDep",
    # Contexte task
    "get_create_task",
    "get_get_task",
    "get_list_tasks",
    "get_list_tasks_by_owner",
    "get_complete_task",
    "get_start_task",
    "get_rename_task",
    "get_delete_task",
    "get_share_task",
    "TaskQueryDep",
    # Contexte user
    "get_create_user",
    "get_get_user",
    "get_list_users",
    "get_rename_user",
]
