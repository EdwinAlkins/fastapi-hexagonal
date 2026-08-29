"""Journalisation des requêtes HTTP, durée de traitement incluse.

Remplace le journal d'accès d'uvicorn (désactivé dans ``infrastructure.logging``)
plutôt que de s'y ajouter : sans cela, chaque requête produirait deux lignes,
l'une avec la durée et l'autre sans.

La durée mesurée est celle passée dans l'application (routage, use case, base,
cache, sérialisation). Elle exclut le temps réseau et le décodage HTTP fait par
uvicorn en amont : c'est un indicateur applicatif, pas la latence vue du client.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("task_manager.access")

# Sondes appelées en boucle par l'orchestrateur (toutes les 30 s pour le
# healthcheck Docker) : journalisées en DEBUG pour ne pas noyer le reste.
QUIET_PATHS = frozenset({"/health"})


def register_request_logging(app: FastAPI) -> None:
    """Enregistre le middleware de journalisation des requêtes."""

    @app.middleware("http")
    async def log_requests(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Une exception non rattrapée doit laisser une trace *chronométrée* :
            # une requête qui échoue après 3 s ne se diagnostique pas comme une
            # qui échoue immédiatement.
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s -> exception après %.1f ms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        # ``url.path`` et non ``url`` : la query string peut porter des données
        # sensibles, qui n'ont rien à faire dans un journal.
        logger.log(
            logging.DEBUG if request.url.path in QUIET_PATHS else logging.INFO,
            "%s %s -> %d en %.1f ms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
