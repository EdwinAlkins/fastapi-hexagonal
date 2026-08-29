"""Exceptions de base du domaine.

Toute erreur métier hérite de :class:`DomainError`. La couche présentation
s'appuie sur cette hiérarchie pour convertir les erreurs en réponses HTTP,
sans que le domaine ait connaissance du protocole HTTP.

Les erreurs sémantiques (introuvable, conflit, validation) sont regroupées ici
dans le *shared kernel* : chaque bounded context spécialise ces bases plutôt que
de redéfinir le lien erreur→statut HTTP, factorisé une fois pour toutes.
"""

from __future__ import annotations


class DomainError(Exception):
    """Erreur métier générique. Racine de toute exception du domaine."""


class ValidationError(DomainError):
    """Une invariante de value object n'est pas respectée."""


class NotFoundError(DomainError):
    """Une ressource référencée par son identité est introuvable."""


class ConflictError(DomainError):
    """L'opération viole une contrainte d'unicité ou d'état."""
