"""
Adaptateur de publication d'événements via RabbitMQ.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

import aio_pika
import orjson

from task_manager.application.shared.messaging import EventPublisherPort

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

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        if not self._channel:
            raise RuntimeError("RabbitMQ non connecté")
        exchange = await self._channel.get_exchange(self._exchange_name)
        message = aio_pika.Message(
            body=orjson.dumps(payload),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(message, routing_key=routing_key)

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
