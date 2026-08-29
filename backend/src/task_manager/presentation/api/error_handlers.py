"""Traduction des exceptions du domaine en réponses HTTP.

Le domaine ignore HTTP ; c'est ici, à la frontière, que l'on décide du code
de statut associé à chaque erreur métier. Le mapping s'appuie sur les *bases
sémantiques* du shared kernel (introuvable, conflit, validation), si bien qu'un
nouveau bounded context est couvert sans toucher ce fichier — il suffit que ses
exceptions héritent de la bonne base.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from task_manager.application.shared.errors import InfrastructureError
from task_manager.domain.shared.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger("task_manager")


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": message})


def register_error_handlers(app: FastAPI) -> None:
    """Enregistre les gestionnaires d'exceptions métier sur l'application.

    FastAPI remonte la hiérarchie des classes : enregistrer les bases suffit à
    couvrir toutes leurs spécialisations (``TaskNotFound``, ``UserNotFound``…).
    """

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return _error(status.HTTP_409_CONFLICT, str(exc))

    @app.exception_handler(ValidationError)
    async def _unprocessable(_: Request, exc: ValidationError) -> JSONResponse:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    # Repli générique : toute autre erreur métier → 400.
    @app.exception_handler(DomainError)
    async def _bad_request(_: Request, exc: DomainError) -> JSONResponse:
        return _error(status.HTTP_400_BAD_REQUEST, str(exc))

    # Erreurs d'infrastructure (dépendance externe indisponible : SMTP, broker…)
    # → 503, et non 500 : le problème est transitoire et côté dépendance, pas une
    # anomalie du service. On journalise (contrairement aux erreurs métier, qui
    # sont attendues) et on ne renvoie pas le détail technique au client.
    @app.exception_handler(InfrastructureError)
    async def _service_unavailable(_: Request, exc: InfrastructureError) -> JSONResponse:
        logger.error("Dépendance technique indisponible : %s", exc, exc_info=exc)
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Une dépendance technique est indisponible.",
        )
