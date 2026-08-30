"""``Task.reconstitute`` : la porte des imports et des restaurations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from task_manager.domain.task.entities import Task
from task_manager.domain.task.exceptions import EmptyTitle, InconsistentTaskState
from task_manager.domain.task.value_objects import TaskId, TaskStatus, TaskTitle
from task_manager.domain.user.value_objects import UserId

CREATED = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
COMPLETED = CREATED + timedelta(hours=3)


def _reconstitute(**overrides: object) -> Task:
    champs: dict[str, object] = {
        "id": TaskId.generate(),
        "owner_id": UserId.generate(),
        "title": TaskTitle("Rédiger le rapport"),
        "description": None,
        "status": TaskStatus.DONE,
        "created_at": CREATED,
        "completed_at": COMPLETED,
    }
    champs.update(overrides)
    return Task.reconstitute(**champs)  # type: ignore[arg-type]


def test_reconstitue_une_tache_terminee_sans_la_recreer() -> None:
    """Le cœur du besoin : ``create`` en est incapable, ``reconstitute`` non."""
    identite = TaskId.generate()

    task = _reconstitute(id=identite)

    assert task.id == identite
    assert task.status is TaskStatus.DONE
    assert task.created_at == CREATED
    assert task.completed_at == COMPLETED


def test_create_ne_sait_pas_representer_une_tache_importee() -> None:
    """Contre-preuve : c'est pourquoi un import ne peut pas passer par ``create``."""
    task = Task.create(owner_id=UserId.generate(), title=TaskTitle("Rédiger le rapport"))

    assert task.status is TaskStatus.TODO
    assert task.completed_at is None
    assert task.created_at > CREATED


def test_refuse_une_tache_terminee_sans_date_de_completion() -> None:
    with pytest.raises(InconsistentTaskState):
        _reconstitute(status=TaskStatus.DONE, completed_at=None)


def test_refuse_une_date_de_completion_sur_une_tache_non_terminee() -> None:
    with pytest.raises(InconsistentTaskState):
        _reconstitute(status=TaskStatus.TODO, completed_at=COMPLETED)


def test_refuse_une_completion_anterieure_a_la_creation() -> None:
    with pytest.raises(InconsistentTaskState):
        _reconstitute(completed_at=CREATED - timedelta(seconds=1))


def test_les_invariants_de_champ_restent_actifs() -> None:
    """Reconstituer n'est pas contourner : les value objects valident toujours."""
    with pytest.raises(EmptyTitle):
        _reconstitute(title=TaskTitle("   "))
