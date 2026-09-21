"""Le mapper SQLAlchemy réutilise la reconstitution du domaine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from task_manager.domain.task.exceptions import InconsistentTaskState
from task_manager.domain.task.value_objects import TaskStatus
from task_manager.infrastructure.persistence.task.mappers import to_domain
from task_manager.infrastructure.persistence.task.models import TaskModel
from task_manager.infrastructure.persistence.user.models import UserModel  # noqa: F401

CREATED = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)


def _model(*, status: str, completed_at: datetime | None) -> TaskModel:
    return TaskModel(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title="Rédiger le rapport",
        description=None,
        status=status,
        created_at=CREATED,
        completed_at=completed_at,
    )


def test_to_domain_reconstitue_un_etat_valide() -> None:
    completed_at = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

    task = to_domain(_model(status=TaskStatus.DONE.value, completed_at=completed_at))

    assert task.status is TaskStatus.DONE
    assert task.completed_at == completed_at


def test_to_domain_refuse_une_ligne_intrinsequement_incoherente() -> None:
    with pytest.raises(InconsistentTaskState):
        to_domain(_model(status=TaskStatus.DONE.value, completed_at=None))
