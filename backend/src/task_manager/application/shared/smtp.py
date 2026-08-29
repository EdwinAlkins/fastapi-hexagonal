"""
Port d'envoi d'e-mails (détail de transport opaque pour l'application).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple


class NotifyResult(NamedTuple):
    """Résultat de la notification par id utilisateur."""

    failed: list[str]


class SMTPSenderPort(ABC):
    """Port permettant à l'application d'envoyer des e-mails."""

    @abstractmethod
    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: str,
    ) -> None: ...
