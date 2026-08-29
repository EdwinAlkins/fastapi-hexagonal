"""Port de cache (préoccupation technique, pas métier).

Il vit dans ``application/`` et non dans ``domain/`` : aucun invariant de
``Task`` ou ``User`` ne dépend du cache — c'est une optimisation de lecture dont
les use cases décident. Le domaine ne connaît que ses ports métier (les
repositories).

Le port parle en ``dict`` (JSON-compatible) et non en DTO : la sérialisation est
l'affaire de l'adaptateur, et le use case reste seul juge de la forme qu'il
range dans le cache.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    """Cache clé/valeur à durée de vie limitée."""

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """Retourne la valeur désérialisée, ou ``None`` si absente/expirée."""

    @abstractmethod
    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        """Enregistre ``value``. ``ttl`` en secondes ; ``None`` → TTL par défaut."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Supprime la clé (no-op si elle n'existe pas)."""

    @abstractmethod
    async def ping(self) -> bool:
        """Vérifie la connexion au cache."""
