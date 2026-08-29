"""Utilitaires de conversion partagés par les mappers ORM↔domaine."""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Garantit un datetime aware en UTC.

    PostgreSQL (``timestamptz`` + asyncpg) renvoie déjà des datetimes aware :
    ce garde-fou ne joue que pour une valeur naïve arrivée d'ailleurs (fixture,
    donnée migrée), afin que le domaine ne manipule jamais d'heure ambiguë.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
