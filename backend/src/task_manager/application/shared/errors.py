"""Erreurs d'infrastructure vues par la couche application.

Symétrique de ``domain/shared/exceptions.py::DomainError`` : ``InfrastructureError``
est la base des échecs *techniques* (transport e-mail, broker, cache…) qui remontent
à travers les ports. Les distinguer des erreurs métier permet, côté présentation, de
les mapper différemment (typiquement 5xx) sans confondre « la demande est invalide »
et « une dépendance externe est indisponible ».
"""

from __future__ import annotations


class InfrastructureError(Exception):
    """Base des erreurs techniques traversant un port (détail de transport opaque)."""


class EmailSendError(InfrastructureError):
    """Échec d'envoi d'e-mail (détail transport opaque pour le use case)."""
