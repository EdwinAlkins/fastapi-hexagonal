"""Chemin d'**écriture en masse** du contexte ``user``.

Pendant de ``application/task/bulk.py``. Il existe parce que l'export des tâches
est dénormalisé : chaque ligne transporte son propriétaire, et importer ce fichier
dans un déploiement vierge suppose donc de recréer les utilisateurs avant les
tâches — sans quoi la clé étrangère rejette tout.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import UserId


class UserBulkWriterPort(ABC):
    """Écriture groupée d'utilisateurs déjà reconstitués."""

    @abstractmethod
    async def save_all(self, users: Sequence[User]) -> BulkWriteResult:
        """Insère un lot en ignorant ce qui existe déjà.

        « Existe déjà » couvre ici **deux** contraintes, pas une : l'identité
        (clé primaire) et l'unicité de l'e-mail. Un utilisateur dont l'e-mail est
        pris par une autre identité est ignoré, pas remonté en erreur — il ne doit
        pas faire échouer les 999 autres lignes du lot.
        """

    @abstractmethod
    async def existing_ids(self, user_ids: Sequence[UserId]) -> set[UserId]:
        """Parmi ces identités, lesquelles sont réellement en base ?

        Un port d'écriture qui pose une question, c'est inhabituel — mais c'est le
        seul moyen de savoir si une tâche peut être insérée. ``ON CONFLICT DO
        NOTHING`` absorbe les conflits d'unicité ; il **n'absorbe pas** les
        violations de clé étrangère, qui font échouer l'``INSERT`` entier. Un
        propriétaire écarté (e-mail déjà pris par une autre identité) emporterait
        donc les 999 tâches du lot.

        Une requête par **lot**, jamais par ligne — et seulement quand un doute
        existe, c'est-à-dire quand au moins un utilisateur n'a pas été inséré.
        """
