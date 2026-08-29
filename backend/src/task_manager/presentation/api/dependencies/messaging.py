"""Câblage du Message Adapter.

Le client est créé et connecté au lifespan, puis rangé dans ``app.state``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from task_manager.application.shared.messaging import EventPublisherPort


def get_message_adapter(request: Request) -> EventPublisherPort:
    adapter: EventPublisherPort = request.app.state.message_adapter
    return adapter


MessageAdapterDep = Annotated[EventPublisherPort, Depends(get_message_adapter)]
