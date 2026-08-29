"""Tests unitaires des value objects du contexte ``task`` (purs, sans I/O).

Les value objects s'auto-valident à la construction : un objet qui existe est
donc toujours valide (« always-valid domain model »). Ces tests verrouillent
cette propriété invariant par invariant.
"""

from __future__ import annotations

import pytest

from task_manager.domain.task.exceptions import EmptyTitle, InvalidTaskId, TitleTooLong
from task_manager.domain.task.value_objects import (
    TITLE_MAX_LENGTH,
    TaskId,
    TaskStatus,
    TaskTitle,
)


class TestTaskId:
    def test_generate_is_unique(self) -> None:
        assert TaskId.generate() != TaskId.generate()

    def test_generate_is_time_ordered(self) -> None:
        # Propriété d'UUIDv7 dont dépend la localité d'index en base : des
        # identités générées à la suite doivent être croissantes, si bien que les
        # insertions se font en fin de B-tree au lieu de le fragmenter.
        ids = [TaskId.generate() for _ in range(100)]
        assert ids == sorted(ids, key=lambda task_id: task_id.value)

    def test_generate_uses_uuid_version_7(self) -> None:
        assert TaskId.generate().value.version == 7

    def test_roundtrips_through_its_string_form(self) -> None:
        original = TaskId.generate()
        assert TaskId.from_string(str(original)) == original

    def test_from_string_rejects_an_invalid_uuid(self) -> None:
        # Erreur *métier* (``InvalidTaskId``) plutôt qu'une ``ValueError`` brute :
        # la frontière traduit l'entrée illisible en langage du domaine.
        with pytest.raises(InvalidTaskId):
            TaskId.from_string("not-a-uuid")

    def test_error_carries_the_offending_value(self) -> None:
        with pytest.raises(InvalidTaskId) as excinfo:
            TaskId.from_string("not-a-uuid")
        assert excinfo.value.raw == "not-a-uuid"

    def test_equality_is_by_value(self) -> None:
        original = TaskId.generate()
        assert TaskId.from_string(str(original)) == original
        assert original != TaskId.generate()

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            TaskId.generate().value = TaskId.generate().value  # type: ignore[misc]


class TestTaskTitle:
    def test_trims_surrounding_whitespace(self) -> None:
        assert TaskTitle("  Ranger le bureau  ").value == "Ranger le bureau"

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
    def test_rejects_empty(self, raw: str) -> None:
        with pytest.raises(EmptyTitle):
            TaskTitle(raw)

    def test_rejects_longer_than_the_maximum(self) -> None:
        with pytest.raises(TitleTooLong):
            TaskTitle("x" * (TITLE_MAX_LENGTH + 1))

    def test_length_is_checked_after_trimming(self) -> None:
        # Les espaces sont retirés avant la mesure : un titre à la longueur limite,
        # entouré d'espaces, reste valide (les espaces ne comptent pas).
        padded = "  " + "x" * TITLE_MAX_LENGTH + "  "
        assert len(TaskTitle(padded).value) == TITLE_MAX_LENGTH

    def test_str_returns_the_title(self) -> None:
        assert str(TaskTitle("Ranger le bureau")) == "Ranger le bureau"

    def test_equality_is_by_value(self) -> None:
        # La normalisation (trim) fait qu'un titre entouré d'espaces est *égal*
        # au même titre déjà nettoyé.
        assert TaskTitle("  Ranger  ") == TaskTitle("Ranger")
        assert TaskTitle("Ranger") != TaskTitle("Trier")

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            TaskTitle("Ranger").value = "Trier"  # type: ignore[misc]


class TestTaskStatus:
    def test_exposes_the_full_lifecycle(self) -> None:
        assert {status.value for status in TaskStatus} == {"todo", "in_progress", "done"}
