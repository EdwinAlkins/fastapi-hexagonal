"""Lecture du fichier NDJSON par l'adaptateur CLI.

Seule vraie logique de la commande : elle décide ce qui est *lisible*, et ce qui
ne l'est pas ne doit ni remonter en exception ni disparaître en silence.
"""

from __future__ import annotations

from pathlib import Path

import click
import orjson
import pytest

from task_manager.presentation.cli.app import _lire

LIGNE = {
    "task_id": "01930000-0000-7000-8000-000000000001",
    "title": "Rédiger le rapport",
    "description": "Trois pages, pas plus.",
    "status": "todo",
    "created_at": "2026-01-15T09:00:00+00:00",
    "completed_at": None,
    "owner_id": "01930000-0000-7000-8000-000000000002",
    "owner_name": "Ada Lovelace",
    "owner_email": "ada@example.com",
}


def _fichier(tmp_path: Path, *lignes: bytes) -> Path:
    chemin = tmp_path / "export.ndjson"
    chemin.write_bytes(b"\n".join(lignes) + b"\n")
    return chemin


def test_lit_une_ligne_par_tache(tmp_path: Path) -> None:
    chemin = _fichier(tmp_path, orjson.dumps(LIGNE), orjson.dumps(LIGNE))
    illisibles: list[int] = []

    rows = list(_lire(chemin, illisibles))

    assert len(rows) == 2
    assert rows[0].title == "Rédiger le rapport"
    assert rows[0].completed_at is None
    assert illisibles == []


def test_ecarte_les_lignes_illisibles_en_notant_leur_numero(tmp_path: Path) -> None:
    chemin = _fichier(
        tmp_path,
        orjson.dumps(LIGNE),
        b"{ceci n'est pas du json",
        orjson.dumps({"task_id": "x"}),  # champs manquants
        orjson.dumps(LIGNE),
    )
    illisibles: list[int] = []

    rows = list(_lire(chemin, illisibles))

    assert len(rows) == 2
    assert illisibles == [2, 3]


def test_ignore_les_lignes_vides(tmp_path: Path) -> None:
    chemin = _fichier(tmp_path, orjson.dumps(LIGNE), b"", b"   ", orjson.dumps(LIGNE))
    illisibles: list[int] = []

    assert len(list(_lire(chemin, illisibles))) == 2
    assert illisibles == []


def test_la_lecture_est_paresseuse(tmp_path: Path) -> None:
    """Le générateur ne doit rien matérialiser : la mémoire ne suit pas le volume."""
    chemin = _fichier(tmp_path, *[orjson.dumps(LIGNE)] * 100)

    flux = _lire(chemin, [])
    premier = next(flux)

    assert premier.owner_name == "Ada Lovelace"


def test_lit_aussi_un_tableau_json(tmp_path: Path) -> None:
    """Le format que produit le bouton « Exporter » du frontend.

    Sans ce cas, un fichier téléchargé depuis l'interface est inimportable par le
    CLI de ce même dépôt — ce qui était le cas avant ce test.
    """
    chemin = tmp_path / "taches.json"
    chemin.write_bytes(orjson.dumps([LIGNE, LIGNE], option=orjson.OPT_INDENT_2))
    illisibles: list[int] = []

    rows = list(_lire(chemin, illisibles))

    assert len(rows) == 2
    assert rows[0].owner_email == "ada@example.com"
    assert illisibles == []


def test_signale_les_elements_incomplets_dun_tableau(tmp_path: Path) -> None:
    chemin = tmp_path / "taches.json"
    chemin.write_bytes(orjson.dumps([LIGNE, {"task_id": "x"}, "pas un objet", LIGNE]))
    illisibles: list[int] = []

    assert len(list(_lire(chemin, illisibles))) == 2
    assert illisibles == [2, 3]


def test_un_tableau_vide_ne_produit_rien(tmp_path: Path) -> None:
    chemin = tmp_path / "taches.json"
    chemin.write_bytes(b"[]")

    assert list(_lire(chemin, [])) == []


def test_refuse_un_json_qui_nest_ni_tableau_ni_ndjson(tmp_path: Path) -> None:
    chemin = tmp_path / "taches.json"
    chemin.write_bytes(b'{"pas": "une liste"}')

    with pytest.raises((click.ClickException, StopIteration)):
        next(iter(_lire(chemin, [])))
