"""
Adaptateur de publication d'événements via RabbitMQ.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from types import TracebackType

import aio_pika
import orjson

from task_manager.application.shared.messaging import EventPublisherPort, IntegrationEvent

logger = logging.getLogger(__name__)


class RabbitMQMessageAdapter(EventPublisherPort):
    """Adaptateur pour le client RabbitMQ."""

    def __init__(self, amqp_url: str, exchange_name: str = "task_events"):
        self._amqp_url = amqp_url
        self._exchange_name = exchange_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._amqp_url)
        self._channel = await self._connection.channel()
        # Déclare l'exchange (type direct ou topic selon tes besoins)
        await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        logger.info("Connecté à RabbitMQ")

    async def publish(self, event: IntegrationEvent) -> None:
        """Sérialise l'événement en JSON et le route sur son ``name``.

        C'est ici, et nulle part ailleurs, que le type d'événement devient une
        *clé de routage* AMQP : la couche application ignore ce vocabulaire.
        """
        if not self._channel:
            raise RuntimeError("RabbitMQ non connecté")
        exchange = await self._channel.get_exchange(self._exchange_name)
        message = aio_pika.Message(
            body=orjson.dumps(asdict(event)),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await exchange.publish(message, routing_key=event.name)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
        logger.info("Déconnecté de RabbitMQ")

    async def __aenter__(self) -> RabbitMQMessageAdapter:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
