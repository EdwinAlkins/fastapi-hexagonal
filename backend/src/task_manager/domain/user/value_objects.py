"""Value objects du bounded context ``user``.

Comme dans le contexte ``task``, les value objects sont immuables et s'auto-valident
à la construction (« always-valid domain model »).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from task_manager.domain.user.exceptions import (
    EmptyName,
    InvalidEmail,
    InvalidUserId,
    NameTooLong,
)


@dataclass(frozen=True, slots=True)
class UserId:
    """Identité d'un utilisateur, encapsulant un UUID.

    C'est ce value object — et non l'agrégat ``User`` — que le contexte ``task``
    référence pour matérialiser la relation « une tâche appartient à un user »
    (référence par identité entre agrégats).
    """

    value: uuid.UUID

    @classmethod
    def generate(cls) -> UserId:
        """Génère une nouvelle identité unique, croissante dans le temps.

        UUIDv7 : voir ``TaskId.generate`` pour le pourquoi (localité d'index).
        """
        return cls(uuid.uuid7())

    @classmethod
    def from_string(cls, raw: str) -> UserId:
        """Reconstruit une identité depuis sa représentation textuelle.

        Lève :class:`InvalidUserId` (erreur métier) plutôt qu'une ``ValueError``
        brute lorsque la chaîne n'est pas un UUID valide.
        """
        try:
            return cls(uuid.UUID(raw))
        except ValueError as exc:
            raise InvalidUserId(raw) from exc

    def __str__(self) -> str:
        return str(self.value)


NAME_MAX_LENGTH = 100


@dataclass(frozen=True, slots=True)
class UserName:
    """Nom d'affichage : non vide, borné en longueur, sans espaces superflus."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        if not cleaned:
            raise EmptyName()
        if len(cleaned) > NAME_MAX_LENGTH:
            raise NameTooLong(NAME_MAX_LENGTH)
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Email:
    """Adresse e-mail normalisée (minuscules, sans espaces superflus)."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip().lower()
        try:
            # ``check_deliverability=False`` : validation *syntaxique* seule.
            # Activée (le défaut), la bibliothèque résout les MX du domaine —
            # une I/O réseau au cœur du domaine, qui rendrait la validité d'un
            # e-mail dépendante du DNS : non déterministe, lente, et capable de
            # rejeter une adresse valide sur une simple panne de résolution.
            # Vérifier qu'une adresse *reçoit* du courrier est le rôle d'un
            # adaptateur (envoi d'un e-mail de confirmation), pas d'un VO.
            validate_email(cleaned, check_deliverability=False)
        except EmailNotValidError as exc:
            raise InvalidEmail(cleaned) from exc
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value
