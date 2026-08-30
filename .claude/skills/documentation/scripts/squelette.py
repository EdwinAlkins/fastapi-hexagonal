#!/usr/bin/env python3
"""Crée la coquille d'un nouveau chapitre et le câble dans la navigation.

    python3 squelette.py 10 ecritures-en-masse "Écrire en masse" --ecrire

Génère la page HTML (en-tête, sidenav, pager, pied) et le fichier markdown, puis
insère l'entrée dans le sidenav de **toutes** les pages du cours et corrige les
pagers voisins. Le sidenav est recopié dans chaque page : toute entrée nouvelle
est un balayage complet, et l'oublier sur une seule page ne se voit qu'à l'œil.

Le **contenu** reste à écrire à la main : ce dépôt n'a pas de générateur
markdown → HTML, et une tentative de conversion semi-automatique s'est déjà
soldée par une boucle infinie. Les deux versions sont rédigées séparément ;
``verifier.py`` contrôle qu'elles restent en correspondance.

Le numéro doit être **libre** : utiliser ``renumeroter.py`` avant, si besoin.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from commun import GRIS, RAZ, ROUGE, VERT, chapitres_html, cours_html, cours_md, racine

R = racine()
ECRIRE = "--ecrire" in sys.argv


def voisins(numero: int) -> tuple[Path | None, Path | None]:
    pages = chapitres_html(R)
    avant = [p for p in pages if int(p.name[:2]) < numero]
    apres = [p for p in pages if int(p.name[:2]) > numero]
    return (avant[-1] if avant else None, apres[0] if apres else None)


def libelle(page: Path) -> str:
    """« 09. Lire sans passer par le domaine », tel qu'un pager l'affiche."""
    m = re.search(r"<h1>(.+?)</h1>", page.read_text(), re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else page.stem


def creer_page(numero: int, slug: str, titre: str) -> str:
    modele = chapitres_html(R)[0]
    source = modele.read_text()
    tete = source[: source.index('<main id="content">')]
    pied = source[source.index("</main>") :]

    tete = re.sub(r"<title>.*?</title>", f"<title>{numero:02d}. {titre} &mdash; FastAPI Hexagonal</title>", tete, count=1)
    tete = re.sub(r'<meta name="description" content="[^"]*">',
                  '<meta name="description" content="TODO — une phrase, ce que le lecteur y gagne.">',
                  tete, count=1)
    # L'entrée de sidenav de ce chapitre n'existe pas encore : c'est ``cabler``
    # qui l'ajoutera, et ``marquer_page_courante`` qui la signalera ensuite.
    tete = tete.replace(' aria-current="page"', "")

    precedent, suivant = voisins(numero)
    pager = ['<nav class="pager">']
    if precedent:
        pager.append(f'  <a href="./{precedent.name}">&larr; {libelle(precedent)}</a>')
    if suivant:
        pager.append(f'  <a href="./{suivant.name}">{libelle(suivant)} &rarr;</a>')
    pager.append("</nav>")

    corps = f"""<main id="content">
<header>
  <h1>{numero:02d}. {titre}</h1>
  <p class="lede">TODO &mdash; l'accroche.</p>
</header>

<div class="tldr">
  <strong>TL;DR</strong> &mdash; TODO
</div>

<!-- TODO : le contenu, à la main. Classes disponibles : note, warn, danger,
     tldr, snippet (avec data-lang), table-wrap, exercises, solutions. -->

<h2 id="à-retenir">À retenir<a class="anchor" href="#à-retenir" aria-label="Lien vers cette section">#</a></h2>

<ul>
  <li>TODO</li>
</ul>

<div class="exercises">
  <h2 id="à-toi-de-jouer">À toi de jouer<a class="anchor" href="#à-toi-de-jouer" aria-label="Lien vers cette section">#</a></h2>
  <ol>
    <li>TODO</li>
  </ol>
  <p class="solutions">&rarr; <a href="./{chapitres_html(R)[-1].name}#chapitre-{numero:02d}">Corrigés</a></p>
</div>

""" + "\n".join(pager) + "\n"
    return tete + corps + pied


def cabler(numero: int, slug: str, court: str) -> None:
    """Insère l'entrée de sidenav dans chaque page, et corrige les pagers voisins."""
    item = f'    <li><a href="./{numero:02d}-{slug}.html"><span class="num">{numero:02d}</span>{court}</a></li>'
    precedent, suivant = voisins(numero)

    for page in sorted(cours_html(R).glob("*.html")):
        lignes = page.read_text().split("\n")
        if any(f'href="./{numero:02d}-{slug}.html"><span' in l for l in lignes):
            continue
        sortie, pose = [], False
        for ligne in lignes:
            est_entree_suivante = (
                suivant
                and re.match(rf'\s*<li><a href="\./{re.escape(suivant.name)}"', ligne)
                and 'class="num"' in ligne
            )
            if not pose and est_entree_suivante:
                sortie.append(item)
                pose = True
            sortie.append(ligne)
        if not pose:  # dernier chapitre : après l'entrée du précédent
            for i, ligne in enumerate(sortie):
                if precedent and re.match(rf'\s*<li><a href="\./{re.escape(precedent.name)}"', ligne) \
                   and 'class="num"' in ligne:
                    sortie.insert(i + 1, item)
                    pose = True
                    break
        if not pose:
            print(f"  {ROUGE}✗{RAZ} {page.name} : point d'insertion introuvable")
            continue
        if ECRIRE:
            page.write_text("\n".join(sortie))

    nouveau = f"{numero:02d}-{slug}.html"
    for voisin, gabarit in ((precedent, '  <a href="./{}">{} &rarr;</a>'),
                            (suivant, '  <a href="./{}">&larr; {}</a>')):
        if not voisin or not ECRIRE:
            continue
        contenu = voisin.read_text()
        bloc = re.search(r'<nav class="pager">(.*?)</nav>', contenu, re.S)
        if not bloc:
            continue
        sens = "&rarr;" if voisin is precedent else "&larr;"
        remplacant = gabarit.format(nouveau, f"{numero:02d}. {court}")
        lignes = bloc.group(1).strip("\n").split("\n")
        index = -1 if voisin is precedent else 0
        lignes[index] = remplacant
        contenu = contenu.replace(bloc.group(1), "\n" + "\n".join(lignes) + "\n")
        voisin.write_text(contenu)


def marquer_page_courante(numero: int, slug: str) -> None:
    """Signale, dans sa propre navigation, la page où l'on se trouve."""
    page = cours_html(R) / f"{numero:02d}-{slug}.html"
    contenu = page.read_text()
    page.write_text(
        contenu.replace(f'<a href="./{numero:02d}-{slug}.html"><span class="num">',
                        f'<a href="./{numero:02d}-{slug}.html" aria-current="page"><span class="num">')
    )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        print(__doc__)
        raise SystemExit(2)
    numero, slug, titre = int(args[0]), args[1], args[2]
    titre_court = args[3] if len(args) > 3 else titre

    if (cours_html(R) / f"{numero:02d}-{slug}.html").exists():
        print(f"{ROUGE}{numero:02d}-{slug} existe déjà.{RAZ}")
        raise SystemExit(1)
    if any(int(p.name[:2]) == numero for p in chapitres_html(R)):
        print(f"{ROUGE}Le numéro {numero:02d} est pris. Lancer renumeroter.py {numero} d'abord.{RAZ}")
        raise SystemExit(1)

    page = creer_page(numero, slug, titre)
    md = f"# {numero:02d}. {titre}\n\n> **TL;DR** — TODO\n\nTODO\n\n## À retenir\n\n- TODO\n\n## À toi de jouer\n\n1. TODO\n\n→ [Corrigés]({chapitres_html(R)[-1].stem}.md#c-corrigés-des-exercices)\n"

    if ECRIRE:
        (cours_html(R) / f"{numero:02d}-{slug}.html").write_text(page)
        (cours_md(R) / f"{numero:02d}-{slug}.md").write_text(md)
    cabler(numero, slug, titre_court)
    if ECRIRE:
        marquer_page_courante(numero, slug)

    print(f"{VERT if ECRIRE else GRIS}{'Créé' if ECRIRE else 'Simulation'} : "
          f"{numero:02d}-{slug} (.md et .html), sidenav et pagers câblés.{RAZ}")
    print(f"""
{GRIS}À faire ensuite :{RAZ}
  · rédiger le contenu, à la main, dans les deux versions
  · vérifier le groupe du sidenav (<h2>) où l'entrée a atterri
  · listes de chapitres  : docs/index.html, docs/cours/index.html
  · tableau des chapitres: backend/docs/cours/README.md
  · comptages            : README.md, docs/index.html (chiffre et lettres)
  · corrigés d'annexes   : nouvelle section « Chapitre {numero:02d} »
  · puis : python3 verifier.py""")
