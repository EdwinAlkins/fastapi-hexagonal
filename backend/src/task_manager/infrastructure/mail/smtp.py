"""
Adaptateur d'envoi d'e-mails via SMTP.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from task_manager.application.shared.errors import EmailSendError
from task_manager.application.shared.smtp import SMTPSenderPort

logger = logging.getLogger(__name__)


class SMTPEmailSenderAdapter(SMTPSenderPort):
    """Adaptateur pour le client SMTP."""

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port

    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: str,
    ) -> None:
        message = EmailMessage()
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body, subtype="html")

        try:
            await aiosmtplib.send(message, hostname=self._host, port=self._port)
        except Exception as e:
            logger.exception("Échec de l'envoi de l'e-mail : %s", e)
            raise EmailSendError(f"Échec de l'envoi de l'e-mail : {e}") from e
