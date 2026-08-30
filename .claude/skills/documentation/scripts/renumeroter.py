#!/usr/bin/env python3
"""Décale les chapitres pour libérer (ou refermer) un numéro.

    python3 renumeroter.py 10            # décale 10..N vers 11..N+1 (insertion)
    python3 renumeroter.py 10 --fermer   # décale 11..N vers 10..N-1 (suppression)
    python3 renumeroter.py 10 --ecrire   # applique

Ce que ce script fait, et qu'un chercher-remplacer sur « 10 » ne peut pas faire :

- il s'indexe sur le **slug** de chaque chapitre, qui est unique, jamais sur son
  numéro — sinon on réécrit au hasard toutes les occurrences du nombre 10 ;
- il traite les fichiers **en ordre décroissant**, sinon 10→11 écraserait le 11
  pas encore déplacé ;
- il corrige le **libellé** des liens en plus de leur cible : « ch. 10 » dans un
  texte de lien reste faux si l'on ne réécrit que le href.

Il ne touche **ni** aux comptages (« 15 chapitres »), **ni** aux listes des index,
**ni** aux corrigés d'annexes : ces endroits sont listés à la fin, à faire à la main.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from commun import GRIS, RAZ, ROUGE, VERT, chapitres_md, cours_html, cours_md, racine, site

R = racine()
ECRIRE = "--ecrire" in sys.argv
FERMER = "--fermer" in sys.argv


def cibles() -> list[Path]:
    """Tout fichier susceptible de citer un chapitre."""
    motifs = ("backend/docs/**/*.md", "backend/README.md", "README.md", "docs/**/*.html")
    vus = {p for m in motifs for p in R.glob(m)}
    return sorted(vus - set(R.glob("backend/docs/.cours-v1/**/*")))


def plan(depuis: int) -> list[tuple[int, int, str]]:
    """(ancien, nouveau, slug), en ordre décroissant pour éviter les collisions."""
    numeros = [(int(p.name[:2]), p.stem[3:]) for p in chapitres_md(R)]
    if FERMER:
        touches = [(n, s) for n, s in numeros if n > depuis]
        return [(n, n - 1, s) for n, s in sorted(touches)]
    touches = [(n, s) for n, s in numeros if n >= depuis]
    return [(n, n + 1, s) for n, s in sorted(touches, reverse=True)]


def appliquer(mouvements: list[tuple[int, int, str]]) -> None:
    for vieux, neuf, slug in mouvements:
        for dossier, ext in ((cours_md(R), "md"), (cours_html(R), "html")):
            src = dossier / f"{vieux:02d}-{slug}.{ext}"
            if src.exists() and ECRIRE:
                src.rename(dossier / f"{neuf:02d}-{slug}.{ext}")

    modifies = 0
    for chemin in cibles() if ECRIRE else []:
        avant = texte = chemin.read_text()
        for vieux, neuf, slug in mouvements:
            v, n = f"{vieux:02d}", f"{neuf:02d}"

            texte = texte.replace(f"{v}-{slug}", f"{n}-{slug}")

            def renommer(m: re.Match[str], v: str = v, n: str = n) -> str:
                return m.group(1) + re.sub(rf"\b{v}\b", n, m.group(2)) + m.group(3)

            texte = re.sub(rf'(<a href="[^"]*{n}-{slug}\.html[^"]*"[^>]*>)(.*?)(</a>)',
                           renommer, texte, flags=re.S)
            texte = re.sub(rf'(\[)((?:[^\]]|\](?!\())*)(\]\([^)]*{n}-{slug}\.md[^)]*\))',
                           renommer, texte)
            # Ancres des corrigés d'annexes : même correspondance que les chapitres.
            texte = re.sub(rf"(annexes\.(?:html|md))#chapitre-{v}\b", rf"\1#chapitre-{n}", texte)
            # Titres du fichier déplacé lui-même.
            if chemin.stem == f"{n}-{slug}":
                texte = re.sub(rf"^# {v}\. ", f"# {n}. ", texte, flags=re.M)
                texte = re.sub(rf"<title>{v}\. ", f"<title>{n}. ", texte)
                texte = re.sub(rf"<h1>{v}\. ", f"<h1>{n}. ", texte)
            # Colonne de numéros du tableau de README (séparée du lien).
            texte = re.sub(rf"^\| {v} \| (\[[^\]]+\]\({n}-{slug}\.md\))", rf"| {n} | \1",
                           texte, flags=re.M)
            # Sections de corrigés, *à l'intérieur* des annexes. Les références
            # entrantes sont traitées plus haut ; ce sont les titres et les ``id``
            # qu'il reste à décaler, sans quoi les liens pointent dans le vide.
            if "annexes" in chemin.stem:
                texte = re.sub(rf"^### Chapitre {v}$", f"### Chapitre {n}", texte, flags=re.M)
                texte = texte.replace(f'id="chapitre-{v}"', f'id="chapitre-{n}"')
                texte = texte.replace(f'href="#chapitre-{v}"', f'href="#chapitre-{n}"')
                texte = texte.replace(f">Chapitre {v}<", f">Chapitre {n}<")
        if texte != avant:
            chemin.write_text(texte)
            modifies += 1

    if ECRIRE:
        print(f"\n{VERT}{len(mouvements)} chapitre(s) déplacé(s), "
              f"{modifies} fichier(s) réécrit(s).{RAZ}")


if __name__ == "__main__":
    positionnels = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(positionnels) != 1 or not positionnels[0].isdigit():
        print(__doc__)
        raise SystemExit(2)

    mouvements = plan(int(positionnels[0]))
    if not mouvements:
        print(f"{ROUGE}Aucun chapitre à déplacer.{RAZ}")
        raise SystemExit(1)

    sens = "fermeture" if FERMER else "insertion"
    print(f"Plan ({sens}) :")
    for vieux, neuf, slug in mouvements:
        print(f"  {vieux:02d}-{slug}  →  {neuf:02d}-{slug}")

    appliquer(mouvements)
    if not ECRIRE:
        print(f"\n{GRIS}Simulation. Relancer avec --ecrire.{RAZ}")

    print(f"""
{GRIS}À faire ensuite, que ce script ne touche pas :{RAZ}
  · listes de chapitres  : docs/index.html, docs/cours/index.html
  · tableau des chapitres: backend/docs/cours/README.md
  · comptages            : README.md, docs/index.html (chiffre et lettres)
  · sidenav de chaque page : squelette.py, ou à la main
  · corrigés d'annexes   : ajouter/retirer la section « Chapitre NN »
  · puis : python3 verifier.py""")
