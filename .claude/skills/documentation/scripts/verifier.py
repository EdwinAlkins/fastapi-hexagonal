#!/usr/bin/env python3
"""Vérifie la documentation : structure, liens, parité md/html, navigation, comptages.

    python3 verifier.py            # tout
    python3 verifier.py liens      # une famille seulement

Code de sortie non nul dès qu'un contrôle échoue → utilisable en pre-commit ou CI.
"""

from __future__ import annotations

import html.parser
import re
import sys
from pathlib import Path

from commun import (
    GRIS,
    RAZ,
    ROUGE,
    VERT,
    ancres_html,
    ancres_md,
    chapitres_html,
    chapitres_infra,
    chapitres_md,
    cours_html,
    cours_md,
    infra_html,
    liens_html,
    racine,
    site,
)

R = racine()
ERREURS: list[str] = []


def echec(message: str) -> None:
    ERREURS.append(message)
    print(f"  {ROUGE}✗{RAZ} {message}")


# ── 1. Structure HTML ───────────────────────────────────────────────────────


class _Balises(html.parser.HTMLParser):
    AUTONOMES = {"meta", "link", "br", "img", "hr", "input", "source", "col"}

    def __init__(self) -> None:
        super().__init__()
        self.pile: list[str] = []
        self.desequilibres: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag not in self.AUTONOMES:
            self.pile.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.pile and self.pile[-1] == tag:
            self.pile.pop()
        elif tag in self.pile:
            self.desequilibres.append(tag)


def structure() -> None:
    """Balises équilibrées, ids uniques, classes existantes, aria-current."""
    print("\nStructure HTML")
    css = (site(R) / "assets/style.css").read_text()
    pages = sorted(site(R).rglob("*.html"))

    for page in pages:
        contenu = page.read_text()
        rel = page.relative_to(R)

        analyseur = _Balises()
        analyseur.feed(contenu)
        if analyseur.pile:
            echec(f"{rel} : balises non fermées {analyseur.pile}")
        for tag in analyseur.desequilibres:
            echec(f"{rel} : </{tag}> ferme la mauvaise balise")

        ids = re.findall(r'id="([^"]+)"', contenu)
        for doublon in {i for i in ids if ids.count(i) > 1}:
            echec(f"{rel} : id dupliqué « {doublon} »")

        for classe in {c for a in re.findall(r'class="([^"]+)"', contenu) for c in a.split()}:
            if f".{classe}" not in css:
                echec(f"{rel} : classe « {classe} » absente de style.css")

        if "<title>" not in contenu:
            echec(f"{rel} : pas de <title>")
        if not contenu.endswith("\n"):
            echec(f"{rel} : pas de saut de ligne final")
        # Une page de contenu doit se signaler dans sa propre navigation.
        if page.parent.name in ("cours", "infra") and page.name != "index.html":
            if 'aria-current="page"' not in contenu:
                echec(f"{rel} : aria-current=\"page\" manquant dans le sidenav")

    print(f"  {GRIS}{len(pages)} pages inspectées{RAZ}")


# ── 2. Liens ────────────────────────────────────────────────────────────────


def liens() -> None:
    """Cibles et ancres, côté site HTML puis côté cours markdown."""
    print("\nLiens")

    total = 0
    for page in sorted(site(R).rglob("*.html")):
        contenu = page.read_text()
        propres = ancres_html(contenu)
        for lien in liens_html(contenu):
            total += 1
            chemin, _, fragment = lien.partition("#")
            if not chemin:
                if fragment and fragment not in propres:
                    echec(f"{page.relative_to(R)} → #{fragment} (ancre interne absente)")
                continue
            cible = (page.parent / chemin).resolve()
            if not cible.exists():
                echec(f"{page.relative_to(R)} → {chemin} (fichier absent)")
            elif fragment and fragment not in ancres_html(cible.read_text()):
                echec(f"{page.relative_to(R)} → {lien} (ancre absente)")
    print(f"  {GRIS}{total} liens internes HTML{RAZ}")

    total = 0
    for doc in sorted(cours_md(R).glob("*.md")):
        for cible_nom, fragment in re.findall(r"\]\(([\w./-]+\.md)(?:#([^)]+))?\)", doc.read_text()):
            total += 1
            cible = (doc.parent / cible_nom).resolve()
            if not cible.exists():
                echec(f"{doc.name} → {cible_nom} (fichier absent)")
            elif fragment and fragment not in ancres_md(cible.read_text()):
                echec(f"{doc.name} → {cible_nom}#{fragment} (ancre absente)")
    print(f"  {GRIS}{total} liens markdown{RAZ}")


# ── 3. Parité markdown / HTML ───────────────────────────────────────────────


def parite() -> None:
    """Les deux versions du cours doivent couvrir les mêmes chapitres et sections."""
    print("\nParité markdown / HTML")
    noms_md = {p.stem for p in chapitres_md(R)}
    noms_html = {p.stem for p in chapitres_html(R)}

    for manquant in sorted(noms_md - noms_html):
        echec(f"{manquant} : page HTML manquante")
    for manquant in sorted(noms_html - noms_md):
        echec(f"{manquant} : source markdown manquante")

    for nom in sorted(noms_md & noms_html):
        md = (cours_md(R) / f"{nom}.md").read_text()
        ht = (cours_html(R) / f"{nom}.html").read_text()
        attendues = {a for t in re.findall(r"^#{2,3} +(.+)$", md, re.M) for a in [_ancre(t)]}
        presentes = set(re.findall(r'<h[23] id="([^"]+)"', ht))
        for absente in sorted(attendues - presentes):
            echec(f"{nom} : section « {absente} » absente du HTML")
        for surnumeraire in sorted(presentes - attendues):
            echec(f"{nom} : section « {surnumeraire} » présente en HTML mais pas en markdown")

    print(f"  {GRIS}{len(noms_md & noms_html)} chapitres comparés{RAZ}")


def _ancre(titre: str) -> str:
    from commun import ancre

    return ancre(titre)


# ── 4. Navigation ───────────────────────────────────────────────────────────


def _section_navigable(dossier: Path, pages: list[Path], libelle: str) -> int:
    """Sidenav complet sur chaque page de la section, chaîne des pagers continue.

    Le sidenav est **recopié dans chaque page** : l'oublier sur une seule ne se voit
    qu'à l'œil, et c'est déjà arrivé. D'où ce contrôle, appliqué aux deux sections.
    """
    attendus = [p.stem for p in pages]

    for page in sorted(dossier.glob("*.html")):
        contenu = page.read_text()
        for stem in attendus:
            # La page courante insère aria-current entre le href et le span :
            # une comparaison littérale produirait un faux positif par page.
            if not re.search(rf'href="\./{re.escape(stem)}\.html"[^>]*><span class="num">', contenu):
                echec(f"{libelle}/{page.name} : « {stem} » absent du sidenav")

    # La chaîne doit se dérouler sans trou du premier au dernier chapitre.
    for precedent, suivant in zip(attendus, attendus[1:]):
        contenu = (dossier / f"{precedent}.html").read_text()
        pager = re.search(r'<nav class="pager">(.*?)</nav>', contenu, re.S)
        if not pager:
            echec(f"{libelle}/{precedent} : pas de pager")
        elif f'href="./{suivant}.html"' not in pager.group(1):
            echec(f"{libelle}/{precedent} : le pager ne mène pas à {suivant}")
        contenu = (dossier / f"{suivant}.html").read_text()
        pager = re.search(r'<nav class="pager">(.*?)</nav>', contenu, re.S)
        if pager and f'href="./{precedent}.html"' not in pager.group(1):
            echec(f"{libelle}/{suivant} : le pager ne revient pas à {precedent}")

    return len(attendus)


def navigation() -> None:
    """Sidenav complet partout, et chaîne des pagers continue — cours ET infra."""
    print("\nNavigation")
    n_cours = _section_navigable(cours_html(R), chapitres_html(R), "cours")

    pages_infra = chapitres_infra(R)
    n_infra = _section_navigable(infra_html(R), pages_infra, "infra")
    # Le dernier chapitre infra ne mène pas à un chapitre suivant mais retourne au
    # sommaire de la section : la chaîne du cours ne se transpose pas telle quelle.
    if pages_infra:
        dernier = pages_infra[-1]
        pager = re.search(r'<nav class="pager">(.*?)</nav>', dernier.read_text(), re.S)
        if not pager:
            echec(f"infra/{dernier.stem} : pas de pager")
        elif 'href="./index.html"' not in pager.group(1):
            echec(f"infra/{dernier.stem} : le dernier pager ne revient pas à index.html")

    print(f"  {GRIS}{n_cours} chapitres de cours, {n_infra} chapitres d'infra dans la chaîne{RAZ}")


# ── 5. Comptages ────────────────────────────────────────────────────────────

_LETTRES = {
    13: "Treize", 14: "Quatorze", 15: "Quinze", 16: "Seize", 17: "Dix-sept", 18: "Dix-huit",
}


def comptages() -> None:
    """Le nombre de chapitres est affirmé à quatre endroits : ils doivent concorder."""
    print("\nComptages")
    n = len(chapitres_md(R))
    dernier = f"{n - 1:02d}"

    controles = [
        (R / "README.md", rf"\*\*cours progressif\*\* \({n} chapitres\)", f"« {n} chapitres »"),
        (R / "README.md", rf"chapitres 00 → {dernier}", f"« 00 → {dernier} »"),
        (site(R) / "index.html", rf"Cours de {n} chapitres", f"« Cours de {n} chapitres »"),
    ]
    for fichier, motif, libelle in controles:
        if not re.search(motif, fichier.read_text()):
            echec(f"{fichier.relative_to(R)} : {libelle} attendu")

    lettre = _LETTRES.get(n)
    if lettre and f"{lettre} chapitres" not in (site(R) / "index.html").read_text():
        echec(f"docs/index.html : « {lettre} chapitres » attendu dans le texte")

    # Les listes de chapitres des deux index et du README doivent être complètes.
    for fichier, attendu in (
        (site(R) / "index.html", n),
        (cours_html(R) / "index.html", n),
    ):
        trouve = fichier.read_text().count('<span class="title">')
        if trouve != attendu:
            echec(f"{fichier.relative_to(R)} : {trouve} chapitres listés, {attendu} attendus")

    tableau = (cours_md(R) / "README.md").read_text()
    for page in chapitres_md(R):
        numero = page.name[:2]
        if not re.search(rf"^\| {numero} \| \[[^\]]+\]\({page.name}\)", tableau, re.M):
            echec(f"cours/README.md : ligne « {numero} » absente ou mal numérotée")

    # Section infra : le sommaire doit lister tous les chapitres, ni plus ni moins.
    n_infra = len(chapitres_infra(R))
    index_infra = infra_html(R) / "index.html"
    listes = index_infra.read_text().count('<span class="title">')
    if listes != n_infra:
        echec(f"docs/infra/index.html : {listes} chapitres listés, {n_infra} attendus")

    print(f"  {GRIS}{n} chapitres de cours (00 → {dernier}), {n_infra} d'infra{RAZ}")


FAMILLES = {
    "structure": structure,
    "liens": liens,
    "parite": parite,
    "navigation": navigation,
    "comptages": comptages,
}

if __name__ == "__main__":
    demandees = sys.argv[1:] or list(FAMILLES)
    for nom in demandees:
        if nom not in FAMILLES:
            print(f"Famille inconnue : {nom}. Choix : {', '.join(FAMILLES)}")
            raise SystemExit(2)
        FAMILLES[nom]()

    print()
    if ERREURS:
        print(f"{ROUGE}{len(ERREURS)} problème(s).{RAZ}")
        raise SystemExit(1)
    print(f"{VERT}Documentation cohérente.{RAZ}")
