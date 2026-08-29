"""Point d'entrée ASGI. Lancé via ``uvicorn task_manager.main:app``."""

from __future__ import annotations

from task_manager.presentation.api.app import create_app

app = create_app()
