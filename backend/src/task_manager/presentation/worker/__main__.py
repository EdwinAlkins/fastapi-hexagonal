"""Point d'entrée du worker de notifications e-mail (consumer RabbitMQ)."""

from __future__ import annotations

import asyncio
import logging
import signal

import aio_pika
import orjson

from task_manager.application.shared.smtp import NotifyResult
from task_manager.application.task.dto import ShareTaskNotification
from task_manager.application.task.use_cases.notify_task_shared import NotifyTaskShared
from task_manager.infrastructure.config import get_settings
from task_manager.infrastructure.html_template.shared_mail_renderer import (
    ShareTaskMailTemplateAdapter,
)
from task_manager.infrastructure.logging import configure_logging
from task_manager.infrastructure.mail.smtp import SMTPEmailSenderAdapter
from task_manager.infrastructure.persistence.database import create_engine, create_session_factory
from task_manager.infrastructure.persistence.task.repository import SqlAlchemyTaskRepository
from task_manager.infrastructure.persistence.user.repository import SqlAlchemyUserRepository

logger = logging.getLogger("task_manager.worker")


async def publish_to_dlq(
    dlx: aio_pika.abc.AbstractExchange,
    notification: ShareTaskNotification,
    failed_user_ids: list[str],
    reason: str,
) -> None:
    payload = {
        "task_id": notification.task_id,
        "user_ids": failed_user_ids,
        "subject": notification.subject,
        "body": notification.body,
        "error": reason,
        "source": "notify_task_shared",
    }
    await dlx.publish(
        aio_pika.Message(
            body=orjson.dumps(payload),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key="",
    )


async def process_message(
    incoming: aio_pika.abc.AbstractIncomingMessage,
    use_case: NotifyTaskShared,
    dlx: aio_pika.abc.AbstractExchange,
) -> tuple[ShareTaskNotification, NotifyResult]:
    # ACK uniquement après publish DLQ : sinon perte des échecs si crash entre les deux
    async with incoming.process():
        payload = orjson.loads(incoming.body)
        notification = ShareTaskNotification(**payload)
        logger.info("Reçu message de partage de tâche %s", notification)
        notify_result = await use_case.execute(notification)
        if notify_result.failed:
            await publish_to_dlq(
                dlx,
                notification,
                notify_result.failed,
                reason="smtp_send_failed",
            )
            logger.warning(
                "DLQ: %d destinataire(s) en échec pour task %s",
                len(notify_result.failed),
                notification.task_id,
            )
        return notification, notify_result


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info("Signal d'arrêt reçu, arrêt du worker…")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _request_stop)

    engine = create_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    session_factory = create_session_factory(engine)

    connection = await aio_pika.connect_robust(settings.rabbitmq_url.get_secret_value())
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        settings.exchange_name, aio_pika.ExchangeType.DIRECT, durable=True
    )
    # Deux filets DLQ **complémentaires** (pas redondants), qui alimentent tous
    # deux l'exchange ``email_notifications.dlx`` :
    #   1. DLQ applicative (``publish_to_dlq``) : échecs SMTP *partiels* — le
    #      message est traité et ACK, mais certains destinataires n'ont pas reçu
    #      l'e-mail (``reason="smtp_send_failed"``). Sans ce publish explicite,
    #      ces échecs seraient perdus (le message est ACK, donc jamais dead-letté).
    #   2. DLX native RabbitMQ (``x-dead-letter-exchange`` ci-dessous) : messages
    #      *rejetés* / exceptions non gérées (payload invalide, crash) → RabbitMQ
    #      les dead-lette automatiquement, sans code applicatif.
    dlx = await channel.declare_exchange(
        "email_notifications.dlx",
        aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    dlq = await channel.declare_queue("email_notifications.dlq", durable=True)
    await dlq.bind(dlx)
    queue = await channel.declare_queue(
        "email_notifications",
        durable=True,
        arguments={
            "x-dead-letter-exchange": "email_notifications.dlx",
        },
    )
    await queue.bind(exchange, routing_key="task.shared")

    smtp_sender = SMTPEmailSenderAdapter(host=settings.smtp_host, port=settings.smtp_port)
    email_template = ShareTaskMailTemplateAdapter()

    async def wrapper(incoming: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with session_factory() as session:
            use_case = NotifyTaskShared(
                task_repository=SqlAlchemyTaskRepository(session),
                user_repository=SqlAlchemyUserRepository(session),
                smtp_sender=smtp_sender,
                email_template=email_template,
                from_email=settings.smtp_from_email,
            )
            try:
                _, notify_result = await process_message(incoming, use_case, dlx)
                logger.info("Résultat de la notification par email: %s", notify_result)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    consumer_tag = await queue.consume(wrapper)
    logger.info("Worker en attente de messages…")

    try:
        await stop_event.wait()
    finally:
        logger.info("Arrêt en cours (cancel consumer, fermeture connexions)…")
        await queue.cancel(consumer_tag)
        await connection.close()
        await engine.dispose()
        logger.info("Worker arrêté")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
