"""Use case : importer en masse des tâches et leurs propriétaires."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from task_manager.application.shared.bulk import BulkWriteResult
from task_manager.application.shared.unit_of_work import UnitOfWorkPort
from task_manager.application.task.bulk import TaskBulkWriterPort
from task_manager.application.task.dto import ImportRejection, ImportReport, ImportTaskRow
from task_manager.application.user.bulk import UserBulkWriterPort
from task_manager.domain.shared.exceptions import DomainError
from task_manager.domain.task.entities import Task
from task_manager.domain.task.value_objects import TaskId, TaskStatus, TaskTitle
from task_manager.domain.user.entities import User
from task_manager.domain.user.value_objects import Email, UserId, UserName

DEFAULT_BATCH_SIZE = 1000


class ImportTasks:
    """Rejoue un export de tâches (avec leur propriétaire) dans cette base.

    Trois décisions structurent ce use case.

    **1. On passe par le domaine, mais pas par ``CreateTask``.** Un import est une
    écriture : sauter le domaine reviendrait à déposer dans la base des états que
    personne n'a validés. Mais ``Task.create`` ne sait pas représenter une tâche
    importée — elle impose un identifiant neuf, le statut ``TODO`` et l'instant
    présent, ce qui réécrirait silencieusement les trois choses qui comptent. La
    bonne porte est ``Task.reconstitute`` : les value objects valident toujours,
    seules les règles de *transition* ne sont pas rejouées.

    **2. Le domaine n'est pas le coût.** Construire 100 000 agrégats est du CPU pur,
    de l'ordre de la seconde. Ce qui coûte, ce sont les allers-retours : le chemin
    unitaire (``CreateTask`` → ``users.exists()``, puis ``repository.save()`` →
    ``session.get()``, puis l'``INSERT``) en fait **trois par ligne**, soit 300 000
    requêtes pour 100 000 tâches. On garde donc le domaine en mémoire et on groupe
    les I/O — c'est le même geste qu'en lecture, mais côté écriture.

    **3. Le contrôle inter-agrégats disparaît au lieu d'être groupé.** ``CreateTask``
    vérifie l'existence du propriétaire par une requête. Ici, l'export étant
    dénormalisé, chaque ligne *porte* son propriétaire : on l'insère avant la tâche,
    et la question « ce user existe-t-il ? » ne se pose plus du tout. Une requête
    groupée aurait déjà été un progrès ; zéro requête est mieux.

    L'unité de traitement est la **ligne** : si le propriétaire d'une ligne est
    invalide, la ligne entière est rejetée. Refuser la tâche mais garder le user (ou
    l'inverse) laisserait entrer une moitié de donnée douteuse.
    """

    def __init__(
        self,
        tasks: TaskBulkWriterPort,
        users: UserBulkWriterPort,
        uow: UnitOfWorkPort,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._tasks = tasks
        self._users = users
        self._uow = uow
        self._batch_size = batch_size

    async def execute(self, rows: Iterable[ImportTaskRow]) -> ImportReport:
        """Importe le flux de lignes, lot par lot, et rend le bilan.

        ``rows`` est consommé **paresseusement** : un générateur qui lit un fichier
        ligne à ligne suffit, et la mémoire ne dépend pas de la taille du fichier —
        symétrique du streaming de l'export.
        """
        rows_read = 0
        users_total = BulkWriteResult.empty()
        tasks_total = BulkWriteResult.empty()
        rejections: list[ImportRejection] = []
        # Les identités déjà vues dans les lots précédents : sans ce garde-fou, un
        # doublon à cheval sur deux lots repasserait en base et gonflerait
        # ``skipped`` au lieu d'être signalé comme doublon du fichier.
        seen: set[str] = set()

        for batch in self._batches(rows):
            rows_read += len(batch)
            users, tasks = self._reconstitute(batch, seen, rejections)

            users_written = await self._users.save_all(users)
            users_total += users_written
            retenues = await self._sans_orphelines(users, users_written, tasks, rejections)
            tasks_total += await self._tasks.save_all(retenues)
            # Le lot est acquis : une interruption après ce point ne le reperdra pas,
            # et le rejouer sera sans effet (écritures idempotentes).
            await self._uow.commit()

        return ImportReport(
            rows_read=rows_read,
            users=users_total,
            tasks=tasks_total,
            rejections=rejections,
        )

    async def _sans_orphelines(
        self,
        users: list[User],
        users_written: BulkWriteResult,
        tasks: list[tuple[int, Task]],
        rejections: list[ImportRejection],
    ) -> list[Task]:
        """Écarte les tâches dont le propriétaire n'a pas pu entrer en base.

        Le cas se produit quand un utilisateur du fichier porte un e-mail déjà
        détenu par une **autre** identité : il est ignoré, et sa tâche violerait
        alors la clé étrangère — ce qu'``ON CONFLICT`` ne rattrape pas, contrairement
        aux conflits d'unicité. Sans ce filtre, une ligne douteuse ferait échouer
        tout le lot.

        La question n'est posée que si un utilisateur a été ignoré. Sur un import
        dans une base vierge — le cas courant — le lot ne coûte donc toujours que
        deux ``INSERT`` et aucune lecture.
        """
        if not tasks or not users_written.skipped:
            # Aucun utilisateur ignoré : ils sont tous en base, donc aucune tâche
            # ne peut être orpheline. On ne pose pas la question.
            return [task for _, task in tasks]

        presents = await self._users.existing_ids([user.id for user in users])
        retenues: list[Task] = []
        for line, task in tasks:
            if task.owner_id in presents:
                retenues.append(task)
            else:
                rejections.append(
                    ImportRejection(
                        line=line,
                        task_id=str(task.id),
                        reason="propriétaire refusé : e-mail déjà utilisé par une autre identité",
                    )
                )
        return retenues

    def _batches(self, rows: Iterable[ImportTaskRow]) -> Iterator[list[tuple[int, ImportTaskRow]]]:
        """Découpe le flux en lots numérotés, sans jamais le matérialiser en entier.

        Le numéro est le **rang dans le flux reçu**. Il coïncide avec la ligne du
        fichier tant que l'appelant les transmet toutes ; à lui de signaler à part
        celles qu'il n'a pas su lire.
        """
        batch: list[tuple[int, ImportTaskRow]] = []
        for offset, row in enumerate(rows, start=1):
            batch.append((offset, row))
            if len(batch) >= self._batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def _reconstitute(
        self,
        batch: list[tuple[int, ImportTaskRow]],
        seen: set[str],
        rejections: list[ImportRejection],
    ) -> tuple[list[User], list[tuple[int, Task]]]:
        """Traduit un lot de lignes en agrégats, en écartant ce qui ne tient pas.

        La déduplication des utilisateurs est faite ici, en mémoire : un export de
        100 000 tâches pour 10 000 propriétaires ne doit pas produire 100 000
        insertions d'utilisateurs. Elle est aussi nécessaire techniquement — un même
        identifiant deux fois dans un seul ``INSERT`` est une erreur, pas un conflit.
        """
        users: dict[str, User] = {}
        tasks: list[tuple[int, Task]] = []

        for line, row in batch:
            if row.task_id in seen:
                rejections.append(
                    ImportRejection(
                        line=line, task_id=row.task_id, reason="doublon dans le fichier"
                    )
                )
                continue
            try:
                user = self._to_user(row)
                task = self._to_task(row)
            except DomainError as exc:
                # Les exceptions du domaine portent déjà un message métier lisible :
                # on le transmet tel quel plutôt que de le reformuler.
                rejections.append(ImportRejection(line=line, task_id=row.task_id, reason=str(exc)))
                continue
            except ValueError as exc:
                # Hors du vocabulaire du domaine : date ISO 8601 illisible, ou
                # statut absent de l'énumération.
                rejections.append(
                    ImportRejection(
                        line=line, task_id=row.task_id, reason=f"valeur invalide : {exc}"
                    )
                )
                continue

            seen.add(row.task_id)
            users[row.owner_id] = user
            tasks.append((line, task))

        return list(users.values()), tasks

    @staticmethod
    def _to_user(row: ImportTaskRow) -> User:
        return User.reconstitute(
            id=UserId.from_string(row.owner_id),
            name=UserName(row.owner_name),
            email=Email(row.owner_email),
            # L'export ne transporte pas la date de création du propriétaire ; on
            # retient celle de sa tâche, qui lui est nécessairement postérieure.
            created_at=_parse(row.created_at),
        )

    @staticmethod
    def _to_task(row: ImportTaskRow) -> Task:
        return Task.reconstitute(
            id=TaskId.from_string(row.task_id),
            owner_id=UserId.from_string(row.owner_id),
            title=TaskTitle(row.title),
            description=row.description,
            status=TaskStatus(row.status),
            created_at=_parse(row.created_at),
            completed_at=_parse(row.completed_at) if row.completed_at else None,
        )


def _parse(raw: str) -> datetime:
    """ISO 8601 → ``datetime``. Lève ``ValueError`` si la chaîne est illisible."""
    return datetime.fromisoformat(raw)
