"""Tests unitaires de l'agrégat ``User`` : factory, identité, égalité.

L'agrégat ne charge *jamais* ses tâches (relation 1→n servie par une requête du
contexte ``task``) : rien ici ne navigue vers ``Task``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserId, UserName

A_NAME = UserName("Ada")
AN_EMAIL = Email("ada@example.com")


def _new_user(*, name: UserName = A_NAME, email: Email = AN_EMAIL) -> User:
    return User.create(name=name, email=email)


class TestCreate:
    def test_carries_the_provided_values(self) -> None:
        user = _new_user(name=UserName("Grace"), email=Email("grace@example.com"))
        assert user.name == UserName("Grace")
        assert user.email == Email("grace@example.com")

    def test_generates_a_fresh_identity(self) -> None:
        # Identité issue du domaine (``UserId.generate``), sans aller-retour en base.
        assert isinstance(_new_user().id, UserId)
        assert _new_user().id != _new_user().id

    def test_stamps_an_aware_utc_timestamp(self) -> None:
        before = datetime.now(UTC)
        user = _new_user()
        after = datetime.now(UTC)

        assert user.created_at.tzinfo is not None
        assert before <= user.created_at <= after


class TestRename:
    def test_replaces_the_name(self) -> None:
        user = _new_user()
        user.rename(UserName("Grace"))
        assert user.name == UserName("Grace")

    def test_leaves_the_identity_and_email_untouched(self) -> None:
        user = _new_user()
        identity, email = user.id, user.email

        user.rename(UserName("Grace"))

        assert (user.id, user.email) == (identity, email)


class TestEquality:
    def test_two_users_with_the_same_id_are_equal(self) -> None:
        # Égalité d'entité : l'identité seule, indépendamment du nom ou de l'e-mail.
        left, right = _new_user(), _new_user(name=UserName("Grace"))
        left.id = right.id
        assert left == right
        assert hash(left) == hash(right)

    def test_differs_by_identity(self) -> None:
        assert _new_user() != _new_user()

    def test_is_not_equal_to_another_type(self) -> None:
        assert _new_user() != "ada@example.com"
