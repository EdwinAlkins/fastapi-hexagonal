"""``ImportTasks`` : groupement, idempotence, et rejets ligne à ligne."""

from __future__ import annotations

from task_manager.application.task.dto import ImportTaskRow
from task_manager.application.task.use_cases.import_tasks import ImportTasks
from task_manager.domain.user.value_objects import UserId

from ._fakes import FakeTaskBulkWriter, FakeUnitOfWork, FakeUserBulkWriter

OWNER = str(UserId.generate())


def _row(**overrides: str | None) -> ImportTaskRow:
    champs: dict[str, str | None] = {
        "task_id": str(UserId.generate()),
        "title": "Rédiger le rapport",
        "description": "Trois pages, pas plus.",
        "status": "todo",
        "created_at": "2026-01-15T09:00:00+00:00",
        "completed_at": None,
        "owner_id": OWNER,
        "owner_name": "Ada Lovelace",
        "owner_email": "ada@example.com",
    }
    champs.update(overrides)
    return ImportTaskRow(**champs)  # type: ignore[arg-type]


def _use_case(
    **kwargs: int,
) -> tuple[ImportTasks, FakeTaskBulkWriter, FakeUserBulkWriter, FakeUnitOfWork]:
    tasks, users, uow = FakeTaskBulkWriter(), FakeUserBulkWriter(), FakeUnitOfWork()
    return ImportTasks(tasks=tasks, users=users, uow=uow, **kwargs), tasks, users, uow


async def test_importe_les_taches_et_leurs_proprietaires() -> None:
    use_case, tasks, users, _ = _use_case()

    rapport = await use_case.execute([_row(), _row(), _row()])

    assert rapport.rows_read == 3
    assert rapport.tasks.inserted == 3
    # Les trois lignes partagent un propriétaire : il n'est inséré qu'une fois.
    assert rapport.users.inserted == 1
    assert len(users.stored) == 1
    assert len(tasks.stored) == 3
    assert rapport.rejected == 0


async def test_deduplique_les_proprietaires_dans_un_lot() -> None:
    """100 000 tâches pour 10 000 users ne doivent pas faire 100 000 insertions."""
    use_case, _, users, _ = _use_case()
    autre = str(UserId.generate())

    await use_case.execute([_row(), _row(), _row(owner_id=autre, owner_email="grace@example.com")])

    assert users.batches == [2]


async def test_groupe_les_ecritures_et_committe_par_lot() -> None:
    """Le geste central : N lignes → N/batch_size allers-retours, pas N."""
    use_case, tasks, _, uow = _use_case(batch_size=10)

    rapport = await use_case.execute([_row() for _ in range(25)])

    assert rapport.tasks.inserted == 25
    assert tasks.batches == [10, 10, 5]
    assert uow.commits == 3


async def test_rejouer_un_import_ne_duplique_rien() -> None:
    """Idempotence : c'est ce qui rend une reprise après interruption inoffensive."""
    use_case, tasks, _, _ = _use_case()
    lignes = [_row(), _row()]

    premier = await use_case.execute(lignes)
    second = await use_case.execute(lignes)

    assert premier.tasks.inserted == 2
    assert second.tasks.inserted == 0
    assert second.tasks.skipped == 2
    assert len(tasks.stored) == 2


async def test_une_ligne_invalide_ne_condamne_pas_le_lot() -> None:
    """Le tout-ou-rien est un mauvais contrat à cette échelle."""
    use_case, tasks, _, _ = _use_case()

    rapport = await use_case.execute(
        [_row(), _row(owner_email="pas-une-adresse"), _row(title="   "), _row()]
    )

    assert rapport.rows_read == 4
    assert rapport.tasks.inserted == 2
    assert rapport.rejected == 2
    assert len(tasks.stored) == 2


async def test_le_rejet_porte_le_rang_et_la_raison() -> None:
    """L'argument le moins évident pour le domaine dans un import : le diagnostic."""
    use_case, _, _, _ = _use_case()

    rapport = await use_case.execute([_row(), _row(owner_email="pas-une-adresse")])

    (rejet,) = rapport.rejections
    assert rejet.line == 2
    assert "e-mail" in rejet.reason.lower()


async def test_rejette_un_etat_incoherent() -> None:
    """``reconstitute`` refuse ce qu'aucun value object ne peut voir seul."""
    use_case, _, _, _ = _use_case()

    rapport = await use_case.execute(
        [_row(status="todo", completed_at="2026-01-15T12:00:00+00:00")]
    )

    assert rapport.tasks.inserted == 0
    assert "incohérent" in rapport.rejections[0].reason.lower()


async def test_rejette_un_statut_hors_enumeration() -> None:
    use_case, _, _, _ = _use_case()

    rapport = await use_case.execute([_row(status="en_cours_de_reflexion")])

    assert rapport.rejected == 1
    assert "valeur invalide" in rapport.rejections[0].reason


async def test_rejette_une_date_illisible() -> None:
    use_case, _, _, _ = _use_case()

    rapport = await use_case.execute([_row(created_at="hier")])

    assert rapport.rejected == 1
    assert "valeur invalide" in rapport.rejections[0].reason


async def test_signale_les_doublons_du_fichier_meme_a_cheval_sur_deux_lots() -> None:
    use_case, tasks, _, _ = _use_case(batch_size=1)
    identique = _row()

    rapport = await use_case.execute([identique, identique])

    assert rapport.tasks.inserted == 1
    assert rapport.rejections[0].reason == "doublon dans le fichier"
    assert len(tasks.stored) == 1


async def test_un_flux_vide_ne_touche_pas_la_base() -> None:
    use_case, tasks, users, uow = _use_case()

    rapport = await use_case.execute([])

    assert rapport.rows_read == 0
    assert (tasks.batches, users.batches, uow.commits) == ([], [], 0)
