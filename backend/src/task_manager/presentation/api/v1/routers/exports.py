"""Exports — le **chemin de lecture** exposé en HTTP.

Un router à part, et pas une route de plus sous ``/tasks`` : l'URL dit qu'il s'agit
d'un modèle de lecture et non de la ressource ``task``. Accessoirement, ça évite la
collision avec ``GET /tasks/{task_id}``, qui prendrait « export » pour un
identifiant et renverrait un 422 déroutant.

Noter ce que ce fichier ne contient pas : ni use case, ni entité, ni mapper. Le
router appelle le port de lecture, sérialise, et c'est tout.
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator

import orjson
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse

from task_manager.application.task.queries import TaskQueryPort
from task_manager.presentation.api.dependencies import TaskQueryDep

router = APIRouter(prefix="/exports", tags=["exports"])

# NDJSON : un objet JSON par ligne. Contrairement à un tableau JSON, le format se
# lit et s'écrit au fil de l'eau — on n'a jamais besoin d'avoir le tout en mémoire,
# ni côté serveur ni côté client.
NDJSON = "application/x-ndjson"


async def _lignes(queries: TaskQueryPort) -> AsyncIterator[bytes]:
    async for item in queries.stream_with_owner():
        yield orjson.dumps(dataclasses.asdict(item)) + b"\n"


@router.get(
    "/tasks",
    response_class=StreamingResponse,
    summary="Exporte toutes les tâches avec leur propriétaire (NDJSON)",
    responses={200: {"content": {NDJSON: {}}, "description": "Un objet JSON par ligne."}},
)
async def export_tasks(queries: TaskQueryDep) -> StreamingResponse:
    """Diffuse l'export au fil de l'eau, en mémoire constante.

    ⚠️ Le statut HTTP part avec le **premier octet**. Si la base tombe au milieu du
    flux, on ne peut plus renvoyer un 500 : le client reçoit un flux tronqué. C'est
    le prix du streaming, et la raison pour laquelle un export NDJSON se valide en
    comptant les lignes obtenues, pas en se fiant au code de statut.
    """
    return StreamingResponse(
        _lignes(queries),
        media_type=NDJSON,
        headers={"Content-Disposition": 'attachment; filename="tasks-export.ndjson"'},
    )


@router.get("/tasks/count", summary="Nombre de tâches que l'export produirait")
async def count_tasks(queries: TaskQueryDep, response: Response) -> dict[str, int]:
    """Compte côté base. Permet au client d'afficher une progression.

    Deux requêtes distinctes (ce compte, puis le flux) : une tâche créée entre les
    deux fera diverger les chiffres. Acceptable pour un export ; à ne pas utiliser
    comme une garantie.
    """
    response.headers["Cache-Control"] = "no-store"
    return {"count": await queries.count()}
