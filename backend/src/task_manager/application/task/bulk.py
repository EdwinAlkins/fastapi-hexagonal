"""Chemin d'**écriture en masse** du contexte ``task``.

Troisième porte du contexte, à côté du repository (écriture unitaire) et du query
service (lecture). La symétrie avec ``queries.py`` s'arrête vite, et l'écart est
le cœur du sujet :

- un **query service** peut jeter le domaine, parce qu'une lecture n'engage aucun
  invariant ;
- un **bulk writer** ne le peut pas. Il reçoit donc des ``Task`` — de vrais
  agrégats, déjà validés — et n'a le droit d'optimiser que le **transport** vers la
  base, jamais la validation.

Le port dit le besoin (« écrire ce lot »), pas la technique. Que l'adaptateur
choisisse un ``INSERT`` multi-lignes, un ``COPY`` ou une table de transit ne
regarde que l'infrastructure, et peut changer sans toucher au use case.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.domain.task.entities import Task


class TaskBulkWriterPort(ABC):
    """Écriture groupée de tâches déjà reconstituées."""

    @abstractmethod
    async def save_all(self, tasks: Sequence[Task]) -> BulkWriteResult:
        """Insère un lot en ignorant ce qui existe déjà.

        Le contrat est volontairement **idempotent** : une tâche dont l'identité est
        déjà en base est comptée dans ``skipped``, pas écrasée et pas remontée en
        erreur. C'est ce qui rend la reprise d'un import interrompu inoffensive.

        Ne committe pas : le rythme des commits appartient au use case
        (``UnitOfWorkPort``).
        """
