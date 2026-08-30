"""Vocabulaire commun aux écritures en masse.

Les repositories écrivent **un** agrégat à la fois : c'est le bon contrat pour une
requête HTTP, où l'on modifie une chose. Un import en traite des dizaines de
milliers, et le coût bascule alors entièrement du côté des allers-retours réseau.

Ce module ne porte que le résultat d'un lot ; les ports eux-mêmes vivent dans leur
contexte respectif (``application/task/bulk.py``, ``application/user/bulk.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BulkWriteResult:
    """Ce qu'un lot a réellement produit en base.

    La distinction ``inserted`` / ``skipped`` est ce qui rend un import
    **idempotent** : rejouer un fichier déjà importé ne duplique rien et se
    contente de gonfler ``skipped``.
    """

    inserted: int
    skipped: int

    def __add__(self, other: BulkWriteResult) -> BulkWriteResult:
        return BulkWriteResult(
            inserted=self.inserted + other.inserted,
            skipped=self.skipped + other.skipped,
        )

    @classmethod
    def empty(cls) -> BulkWriteResult:
        return cls(inserted=0, skipped=0)
