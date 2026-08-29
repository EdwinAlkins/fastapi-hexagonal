"""
Port de publication d'événements vers un broker de messages asynchrone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EventPublisherPort(ABC):
    """Contrat fonctionnel de publication ; l'adaptateur gère son propre cycle de vie.

    Le port n'expose que ``publish`` : ``connect`` / ``close`` sont un détail
    d'infrastructure (ouverts/fermés dans le ``lifespan`` de l'API ou au démarrage
    du worker), pas une préoccupation de la couche application.
    """

    @abstractmethod
    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None: ...
