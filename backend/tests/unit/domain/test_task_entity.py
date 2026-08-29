"""Tests unitaires de l'agrégat ``Task`` : factory, invariants & transitions d'état.

L'entité est pure (aucune I/O) : ces tests verrouillent son comportement métier
transition par transition, sans passer par la persistance ni le transport HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from task_manager.domain.task.entities import Task
from task_manager.domain.task.exceptions import TaskAlreadyCompleted
from task_manager.domain.task.value_objects import TaskId, TaskStatus, TaskTitle
from task_manager.domain.user.value_objects import UserId

A_TITLE = TaskTitle("Écrire les tests")


def _new_task(
    *,
    owner_id: UserId | None = None,
    title: TaskTitle = A_TITLE,
    description: str | None = None,
) -> Task:
    return Task.create(
        owner_id=owner_id if owner_id is not None else UserId.generate(),
        title=title,
        description=description,
    )


class TestCreate:
    def test_starts_in_todo(self) -> None:
        # Toute tâche naît « à faire » : c'est l'état initial du cycle de vie.
        assert _new_task().status is TaskStatus.TODO

    def test_has_no_completion_timestamp_yet(self) -> None:
        assert _new_task().completed_at is None

    def test_carries_the_owner_reference(self) -> None:
        # Référence par identité vers l'agrégat User (côté « n » de la relation) :
        # la tâche porte un ``UserId``, jamais un objet ``User``.
        owner_id = UserId.generate()
        assert _new_task(owner_id=owner_id).owner_id == owner_id

    def test_carries_the_provided_title(self) -> None:
        assert _new_task(title=TaskTitle("Ranger le bureau")).title == TaskTitle("Ranger le bureau")

    def test_has_no_description_by_default(self) -> None:
        assert _new_task().description is None

    def test_keeps_the_provided_description(self) -> None:
        assert _new_task(description="Avant vendredi").description == "Avant vendredi"

    def test_generates_a_fresh_identity(self) -> None:
        # L'identité vient du domaine (``TaskId.generate``), pas d'un aller-retour
        # en base : deux créations successives ne partagent jamais leur id.
        assert isinstance(_new_task().id, TaskId)
        assert _new_task().id != _new_task().id

    def test_stamps_an_aware_utc_timestamp(self) -> None:
        before = datetime.now(UTC)
        task = _new_task()
        after = datetime.now(UTC)

        assert task.created_at.tzinfo is not None
        assert before <= task.created_at <= after


class TestStart:
    def test_moves_to_in_progress(self) -> None:
        task = _new_task()
        task.start()
        assert task.status is TaskStatus.IN_PROGRESS

    def test_is_idempotent_on_an_already_started_task(self) -> None:
        task = _new_task()
        task.start()
        task.start()
        assert task.status is TaskStatus.IN_PROGRESS

    def test_is_rejected_on_a_completed_task(self) -> None:
        # Une tâche terminée est un état final : on ne la « redémarre » pas.
        task = _new_task()
        task.complete()
        with pytest.raises(TaskAlreadyCompleted):
            task.start()


class TestComplete:
    def test_moves_to_done(self) -> None:
        task = _new_task()
        task.complete()
        assert task.status is TaskStatus.DONE

    def test_stamps_the_completion_timestamp(self) -> None:
        before = datetime.now(UTC)
        task = _new_task()
        task.complete()
        after = datetime.now(UTC)

        assert task.completed_at is not None
        assert task.completed_at.tzinfo is not None
        assert before <= task.completed_at <= after

    def test_can_complete_a_task_in_progress(self) -> None:
        task = _new_task()
        task.start()
        task.complete()
        assert task.status is TaskStatus.DONE

    def test_is_rejected_twice(self) -> None:
        # Invariant métier : on ne complète pas deux fois (le second appel ne doit
        # pas non plus écraser le premier ``completed_at``).
        task = _new_task()
        task.complete()
        with pytest.raises(TaskAlreadyCompleted):
            task.complete()


class TestRename:
    def test_replaces_the_title(self) -> None:
        task = _new_task()
        task.rename(TaskTitle("Nouveau titre"))
        assert task.title == TaskTitle("Nouveau titre")

    def test_leaves_the_identity_and_status_untouched(self) -> None:
        task = _new_task()
        task.start()
        identity, status = task.id, task.status

        task.rename(TaskTitle("Nouveau titre"))

        assert (task.id, task.status) == (identity, status)


class TestEquality:
    def test_two_tasks_with_the_same_id_are_equal(self) -> None:
        # Égalité d'entité : l'identité seule, pas le contenu (titre, statut…).
        identity = TaskId.generate()
        left = Task.create(owner_id=UserId.generate(), title=TaskTitle("Une tâche"))
        right = Task.create(owner_id=UserId.generate(), title=TaskTitle("Une autre"))
        left.id = right.id = identity

        assert left == right
        assert hash(left) == hash(right)

    def test_differs_by_identity(self) -> None:
        assert _new_task() != _new_task()

    def test_is_not_equal_to_another_type(self) -> None:
        assert _new_task() != "une tâche"
