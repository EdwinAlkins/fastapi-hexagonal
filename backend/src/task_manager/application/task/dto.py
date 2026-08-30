"""Objets de transfert (commands & DTO) de la couche application.

Ce sont des structures neutres (dataclasses) qui découplent les use cases
des schémas Pydantic (présentation) et des value objects (domaine).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.application.shared.messaging import IntegrationEvent
from task_manager.domain.task.entities import Task


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Données nécessaires à la création d'une tâche."""

    owner_id: str
    title: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class TaskDTO:
    """Représentation de sortie d'une tâche, indépendante du transport."""

    id: str
    owner_id: str
    title: str
    description: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_entity(cls, task: Task) -> TaskDTO:
        """Projette un agrégat du domaine en DTO de sortie."""
        return cls(
            id=str(task.id),
            owner_id=str(task.owner_id),
            title=str(task.title),
            description=task.description,
            status=task.status.value,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )


@dataclass(frozen=True, slots=True)
class ShareTaskNotification(IntegrationEvent):
    """Événement d'intégration : une tâche vient d'être partagée.

    Publié par ``ShareTask`` et consommé par le worker, qui le passe à
    ``NotifyTaskShared``. C'est le **contrat de message** entre les deux process :
    tout changement de forme doit rester compatible avec un worker encore déployé
    dans l'ancienne version.
    """

    name: ClassVar[str] = "task.shared"

    task_id: str
    user_ids: list[str]
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class ImportTaskRow:
    """Une ligne du fichier d'import, **telle qu'elle arrive du fil**.

    Tous les champs sont des ``str`` : c'est la forme du transport, pas celle du
    domaine. La conversion (UUID, date, statut) et son échec éventuel sont traités
    par ``ImportTasks``, de sorte qu'une date illisible produise un *rejet ligne à
    ligne* au lieu de faire exploser tout l'import.

    Miroir de ``TaskWithOwner`` (le DTO d'export), et ce couplage est un défaut
    assumé : réutiliser un modèle de **lecture** comme format d'échange lie le
    chemin d'import à l'affichage. ``description`` en est l'illustration retournée
    — le champ a été ajouté au DTO d'**export** pour que l'aller-retour ne perde
    rien, alors qu'aucun écran ne l'affiche. Le modèle de lecture porte désormais
    une colonne qui ne sert qu'à l'écriture. Le jour où le transfert entre
    déploiements devient une vraie fonctionnalité, il lui faut son propre format,
    versionné.
    """

    task_id: str
    title: str
    description: str | None
    status: str
    created_at: str
    completed_at: str | None
    owner_id: str
    owner_name: str
    owner_email: str


@dataclass(frozen=True, slots=True)
class ImportRejection:
    """Une ligne refusée, et **pourquoi**.

    C'est l'argument le moins évident en faveur du domaine dans un import : un
    ``COPY`` brut sur 100 000 lignes rend une erreur PostgreSQL opaque et s'arrête
    là. Le domaine, lui, sait dire « ligne 47 231 : adresse e-mail invalide », et
    laisse passer les 99 999 autres.
    """

    line: int
    task_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Bilan d'un import : ce qui est entré, ce qui était déjà là, ce qui a été refusé.

    Un import en masse ne répond pas par oui ou par non. Le tout-ou-rien est un
    mauvais contrat à cette échelle : une seule ligne douteuse sur 100 000
    condamnerait le lot entier.
    """

    rows_read: int
    users: BulkWriteResult
    tasks: BulkWriteResult
    rejections: list[ImportRejection]

    @property
    def rejected(self) -> int:
        return len(self.rejections)
