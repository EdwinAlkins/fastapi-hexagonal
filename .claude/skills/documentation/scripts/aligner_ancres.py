#!/usr/bin/env python3
"""Réaligne les ``id`` des pages HTML sur les titres de leur source markdown.

    python3 aligner_ancres.py            # montre ce qui serait changé
    python3 aligner_ancres.py --ecrire   # applique

Les identifiants ne sont pas de la prose : les recopier à la main est une source
d'écart silencieux, surtout quand un titre contient des guillemets, une flèche ou
un tiret cadratin — que la règle d'ancrage supprime en laissant leurs espaces.

Rapproche les titres **par position** dans le document. Refuse d'agir si les deux
versions n'ont pas le même nombre de sections : c'est alors un écart de contenu,
pas d'identifiant, et il se corrige à la main.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from commun import GRIS, RAZ, ROUGE, VERT, ancre, chapitres_md, cours_html, racine

ECRIRE = "--ecrire" in sys.argv
R = racine()


def aligner(source: Path) -> int:
    page = cours_html(R) / f"{source.stem}.html"
    if not page.exists():
        return 0

    attendus = [ancre(t) for t in re.findall(r"^#{2,3} +(.+)$", source.read_text(), re.M)]
    contenu = page.read_text()
    presents = re.findall(r'<h[23] id="([^"]+)"', contenu)

    if len(attendus) != len(presents):
        print(f"  {ROUGE}✗{RAZ} {page.name} : {len(presents)} sections en HTML, "
              f"{len(attendus)} en markdown — écart de contenu, à traiter à la main")
        return 0

    changes = 0
    for vieux, neuf in zip(presents, attendus):
        if vieux == neuf:
            continue
        # L'identifiant et le lien d'ancrage que porte le titre lui-même.
        contenu = contenu.replace(f'id="{vieux}"', f'id="{neuf}"')
        contenu = contenu.replace(f'href="#{vieux}"', f'href="#{neuf}"')
        print(f"  {vieux}\n    → {neuf}")
        changes += 1

    if changes and ECRIRE:
        page.write_text(contenu)
    return changes


if __name__ == "__main__":
    total = sum(aligner(source) for source in chapitres_md(R))
    print()
    if not total:
        print(f"{VERT}Toutes les ancres sont alignées.{RAZ}")
    elif ECRIRE:
        print(f"{VERT}{total} ancre(s) réalignée(s).{RAZ}")
    else:
        print(f"{GRIS}{total} ancre(s) à réaligner. Relancer avec --ecrire.{RAZ}")
