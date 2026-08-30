"""Chemin de **lecture** du contexte ``task`` — distinct du chemin d'écriture.

Les repositories (``domain/task/repository.py``) servent les écritures : ils
parlent en agrégats ``Task``, reconstruisent des value objects et garantissent des
invariants. Rien de tout cela n'est utile pour afficher ou exporter des données :
une projection n'engage aucun invariant.

Ce port est donc l'autre porte, celle des lectures : il rend des **DTO plats**, en
lecture seule, et peut traverser plusieurs agrégats — ici ``Task`` et ``User`` —
précisément parce qu'il ne cherche ni à faire respecter ni à modifier leurs
invariants.

Il vit dans ``application/`` et non dans ``domain/`` : « exporter des tâches avec
leur propriétaire » est un besoin de cas d'usage, pas un concept du modèle métier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TaskWithOwner:
    """Projection de lecture : une tâche et l'essentiel de son propriétaire.

    Volontairement **plate** et en types simples. Ce n'est pas un agrégat, ce n'est
    pas un ``TaskDTO`` : c'est la forme exacte dont l'export a besoin, ni plus ni
    moins. Un DTO de lecture ne doit pas pouvoir être confondu avec une entité.
    """

    task_id: str
    title: str
    description: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None
    owner_id: str
    owner_name: str
    owner_email: str


class TaskQueryPort(ABC):
    """Lectures du contexte ``task``. **Aucune écriture, sans exception.**

    Le jour où une méthode d'écriture apparaît ici, les invariants garantis par les
    agrégats ne valent plus rien : ils seraient contournables par la porte de
    lecture.
    """

    @abstractmethod
    def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]:
        """Parcourt toutes les tâches jointes à leur propriétaire, au fil de l'eau.

        Volontairement **non paginé** : c'est un flux, pas une page. La mémoire
        reste constante quel que soit le volume, ce que le chemin par agrégats ne
        peut structurellement pas offrir — il doit tout matérialiser avant de
        rendre la main.
        """

    @abstractmethod
    async def count(self) -> int:
        """Nombre total de tâches, calculé par la base (``COUNT``), jamais en Python."""
