"""Tests unitaires des value objects du contexte ``user`` (purs, sans I/O).

Comme dans le contexte ``task``, les value objects s'auto-valident à la
construction : un objet qui existe est toujours valide.
"""

from __future__ import annotations

import pytest

from task_manager.domain.user.exceptions import (
    EmptyName,
    InvalidEmail,
    InvalidUserId,
    NameTooLong,
)
from task_manager.domain.user.value_objects import (
    NAME_MAX_LENGTH,
    Email,
    UserId,
    UserName,
)


class TestUserId:
    def test_generate_is_unique(self) -> None:
        assert UserId.generate() != UserId.generate()

    def test_generate_is_time_ordered(self) -> None:
        # Cf. TestTaskId : UUIDv7, insertions ordonnées en fin d'index B-tree.
        ids = [UserId.generate() for _ in range(100)]
        assert ids == sorted(ids, key=lambda user_id: user_id.value)

    def test_generate_uses_uuid_version_7(self) -> None:
        assert UserId.generate().value.version == 7

    def test_roundtrips_through_its_string_form(self) -> None:
        original = UserId.generate()
        assert UserId.from_string(str(original)) == original

    def test_from_string_rejects_an_invalid_uuid(self) -> None:
        with pytest.raises(InvalidUserId):
            UserId.from_string("not-a-uuid")

    def test_error_carries_the_offending_value(self) -> None:
        with pytest.raises(InvalidUserId) as excinfo:
            UserId.from_string("not-a-uuid")
        assert excinfo.value.raw == "not-a-uuid"

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            UserId.generate().value = UserId.generate().value  # type: ignore[misc]


class TestUserName:
    def test_trims_surrounding_whitespace(self) -> None:
        assert UserName("  Ada  ").value == "Ada"

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
    def test_rejects_empty(self, raw: str) -> None:
        with pytest.raises(EmptyName):
            UserName(raw)

    def test_rejects_longer_than_the_maximum(self) -> None:
        with pytest.raises(NameTooLong):
            UserName("x" * (NAME_MAX_LENGTH + 1))

    def test_length_is_checked_after_trimming(self) -> None:
        padded = "  " + "x" * NAME_MAX_LENGTH + "  "
        assert len(UserName(padded).value) == NAME_MAX_LENGTH

    def test_str_returns_the_name(self) -> None:
        assert str(UserName("Ada")) == "Ada"

    def test_equality_is_by_value(self) -> None:
        assert UserName("  Ada  ") == UserName("Ada")
        assert UserName("Ada") != UserName("Grace")

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            UserName("Ada").value = "Grace"  # type: ignore[misc]


class TestEmail:
    def test_normalises_case_and_whitespace(self) -> None:
        assert Email("  Ada@Example.COM ").value == "ada@example.com"

    @pytest.mark.parametrize(
        "raw",
        [
            "",  # vide
            "ada",  # ni « @ » ni domaine
            "ada@",  # domaine manquant
            "@example.com",  # partie locale manquante
            "a b@c.com",  # espace au milieu
        ],
    )
    def test_rejects_invalid(self, raw: str) -> None:
        with pytest.raises(InvalidEmail):
            Email(raw)

    def test_error_carries_the_normalised_value(self) -> None:
        # L'e-mail est d'abord normalisé (trim + minuscules), *puis* validé : c'est
        # cette forme normalisée que l'erreur remonte, pas la saisie brute.
        with pytest.raises(InvalidEmail) as excinfo:
            Email("  NOT-AN-EMAIL  ")
        assert excinfo.value.raw == "not-an-email"

    def test_str_returns_the_address(self) -> None:
        assert str(Email("ada@example.com")) == "ada@example.com"

    def test_equality_is_by_value(self) -> None:
        # La normalisation rend deux saisies différentes de la même adresse égales.
        assert Email("  Ada@Example.COM ") == Email("ada@example.com")
        assert Email("ada@example.com") != Email("grace@example.com")

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            Email("ada@example.com").value = "grace@example.com"  # type: ignore[misc]
