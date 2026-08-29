"""Câblage du SMTP (préoccupation transverse).

L'adaptateur SMTP est sans état : une instance unique est créée au démarrage
(``app.state.smtp_sender``) et réutilisée par toutes les requêtes, plutôt que
réinstanciée à chaque appel.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from task_manager.application.shared.smtp import SMTPSenderPort


def get_smtp(request: Request) -> SMTPSenderPort:
    smtp_sender: SMTPSenderPort = request.app.state.smtp_sender
    return smtp_sender


SMTPSenderDep = Annotated[SMTPSenderPort, Depends(get_smtp)]
