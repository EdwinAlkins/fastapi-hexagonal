"""Endpoints HTTP du bounded context ``user``.

Porte aussi les routes *imbriquées* de la relation 1→n :
``POST /users/{id}/tasks`` (créer une tâche pour ce user) et
``GET /users/{id}/tasks`` (lister ses tâches).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from task_manager.application.task.dto import CreateTaskCommand
from task_manager.application.task.use_cases.create_task import CreateTask
from task_manager.application.task.use_cases.list_tasks_by_owner import ListTasksByOwner
from task_manager.application.user.dto import CreateUserCommand
from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.application.user.use_cases.get_user import GetUser
from task_manager.application.user.use_cases.list_users import ListUsers
from task_manager.application.user.use_cases.rename_user import RenameUser
from task_manager.presentation.api.dependencies import (
    get_create_task,
    get_create_user,
    get_get_user,
    get_list_tasks_by_owner,
    get_list_users,
    get_rename_user,
)
from task_manager.presentation.api.v1.schemas.task import CreateTaskRequest, TaskResponse
from task_manager.presentation.api.v1.schemas.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    use_case: Annotated[CreateUser, Depends(get_create_user)],
) -> UserResponse:
    dto = await use_case.execute(CreateUserCommand(name=payload.name, email=payload.email))
    return UserResponse.from_dto(dto)


@router.get("", response_model=list[UserResponse])
async def list_users(
    use_case: Annotated[ListUsers, Depends(get_list_users)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    dtos = await use_case.execute(limit=limit, offset=offset)
    return [UserResponse.from_dto(dto) for dto in dtos]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    use_case: Annotated[GetUser, Depends(get_get_user)],
) -> UserResponse:
    dto = await use_case.execute(user_id)
    return UserResponse.from_dto(dto)


@router.patch("/{user_id}", response_model=UserResponse)
async def rename_user(
    user_id: str,
    payload: UpdateUserRequest,
    use_case: Annotated[RenameUser, Depends(get_rename_user)],
) -> UserResponse:
    # La mutation invalide l'entrée de cache du user (cf. RenameUser) : la
    # prochaine lecture repartira de la base.
    dto = await use_case.execute(user_id, payload.name)
    return UserResponse.from_dto(dto)


# --- Relation 1→n : tâches d'un utilisateur ---------------------------------


@router.post(
    "/{user_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
async def create_task_for_user(
    user_id: str,
    payload: CreateTaskRequest,
    use_case: Annotated[CreateTask, Depends(get_create_task)],
) -> TaskResponse:
    # Le propriétaire vient du chemin, pas du corps : la tâche naît dans le
    # contexte d'un user. Le use case vérifie que ce user existe (→ 404 sinon).
    dto = await use_case.execute(
        CreateTaskCommand(owner_id=user_id, title=payload.title, description=payload.description)
    )
    return TaskResponse.from_dto(dto)


@router.get("/{user_id}/tasks", response_model=list[TaskResponse], tags=["tasks"])
async def list_user_tasks(
    user_id: str,
    use_case: Annotated[ListTasksByOwner, Depends(get_list_tasks_by_owner)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskResponse]:
    dtos = await use_case.execute(user_id, limit=limit, offset=offset)
    return [TaskResponse.from_dto(dto) for dto in dtos]
