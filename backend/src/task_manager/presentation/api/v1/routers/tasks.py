"""Endpoints HTTP du bounded context ``task``.

La *création* et le *listing par propriétaire* d'une tâche vivent sous le
routeur ``users`` (routes imbriquées ``/users/{id}/tasks``), car une tâche
existe toujours dans le contexte d'un utilisateur. Ce routeur-ci porte les
opérations qui ne dépendent que de la tâche elle-même.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from task_manager.application.task.use_cases.complete_task import CompleteTask
from task_manager.application.task.use_cases.delete_task import DeleteTask
from task_manager.application.task.use_cases.get_task import GetTask
from task_manager.application.task.use_cases.list_tasks import ListTasks
from task_manager.application.task.use_cases.rename_task import RenameTask
from task_manager.application.task.use_cases.share_task import ShareTask
from task_manager.application.task.use_cases.start_task import StartTask
from task_manager.presentation.api.dependencies import (
    get_complete_task,
    get_delete_task,
    get_get_task,
    get_list_tasks,
    get_rename_task,
    get_share_task,
    get_start_task,
)
from task_manager.presentation.api.v1.schemas.task import (
    ShareTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    use_case: Annotated[ListTasks, Depends(get_list_tasks)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskResponse]:
    dtos = await use_case.execute(limit=limit, offset=offset)
    return [TaskResponse.from_dto(dto) for dto in dtos]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    use_case: Annotated[GetTask, Depends(get_get_task)],
) -> TaskResponse:
    dto = await use_case.execute(task_id)
    return TaskResponse.from_dto(dto)


@router.patch("/{task_id}", response_model=TaskResponse)
async def rename_task(
    task_id: str,
    payload: UpdateTaskRequest,
    use_case: Annotated[RenameTask, Depends(get_rename_task)],
) -> TaskResponse:
    dto = await use_case.execute(task_id, payload.title)
    return TaskResponse.from_dto(dto)


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: str,
    use_case: Annotated[StartTask, Depends(get_start_task)],
) -> TaskResponse:
    dto = await use_case.execute(task_id)
    return TaskResponse.from_dto(dto)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    use_case: Annotated[CompleteTask, Depends(get_complete_task)],
) -> TaskResponse:
    dto = await use_case.execute(task_id)
    return TaskResponse.from_dto(dto)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    use_case: Annotated[DeleteTask, Depends(get_delete_task)],
) -> None:
    await use_case.execute(task_id)


@router.post("/{task_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def share_task(
    task_id: str,
    payload: ShareTaskRequest,
    use_case: Annotated[ShareTask, Depends(get_share_task)],
) -> None:
    await use_case.execute(task_id, payload.user_ids, payload.subject, payload.body)
