"""
Port de publication d'événements vers un broker de messages asynchrone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    """Fait applicatif destiné à sortir du processus.

    C'est un **contrat public** : sa forme est lue par un autre composant (ici le
    worker), possiblement déployé séparément et dans une version différente. Elle
    se versionne donc et ne se change pas à la légère — ajouter un champ optionnel
    est sûr, en renommer un ne l'est pas.

    À ne pas confondre avec un *événement de domaine*, qui serait émis par
    l'agrégat lui-même et resterait interne au bounded context.

    ``name`` identifie le **type** d'événement indépendamment du transport : c'est
    l'adaptateur qui décide comment le traduire (clé de routage AMQP ici, sujet
    Kafka ou nom de topic ailleurs). Le port reste ainsi libre de tout vocabulaire
    de broker.
    """

    name: ClassVar[str]


class EventPublisherPort(ABC):
    """Contrat fonctionnel de publication ; l'adaptateur gère son propre cycle de vie.

    Le port n'expose que ``publish`` : ``connect`` / ``close`` sont un détail
    d'infrastructure (ouverts/fermés dans le ``lifespan`` de l'API ou au démarrage
    du worker), pas une préoccupation de la couche application.

    Il parle en :class:`IntegrationEvent`, pas en ``dict`` : la forme du message
    est un contrat **typé**, vérifié par mypy et lisible par un humain. La
    *sérialisation* (JSON, protobuf…) et le *routage* restent l'affaire de
    l'adaptateur — c'est lui, et lui seul, qui sait ce qu'est une clé de routage.
    """

    @abstractmethod
    async def publish(self, event: IntegrationEvent) -> None: ...
