"""Helpers partagés par les scripts de documentation.

Un seul endroit pour les règles qui se sont révélées piégeuses à l'usage :
la fabrication des ancres, et la localisation des fichiers.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# ── Emplacements ────────────────────────────────────────────────────────────


def racine() -> Path:
    """Racine du dépôt, quel que soit le répertoire courant."""
    sortie = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(sortie.stdout.strip())


def cours_md(base: Path | None = None) -> Path:
    """Sources markdown du cours (la version lue depuis GitHub)."""
    return (base or racine()) / "backend/docs/cours"


def cours_html(base: Path | None = None) -> Path:
    """Pages du cours sur le site (la version lue depuis GitHub Pages)."""
    return (base or racine()) / "docs/cours"


def site(base: Path | None = None) -> Path:
    """Racine du site statique publié par GitHub Pages."""
    return (base or racine()) / "docs"


def chapitres_md(base: Path | None = None) -> list[Path]:
    """Chapitres numérotés, dans l'ordre. Exclut README.md."""
    return sorted(cours_md(base).glob("[0-9][0-9]-*.md"))


def chapitres_html(base: Path | None = None) -> list[Path]:
    return sorted(cours_html(base).glob("[0-9][0-9]-*.html"))


def infra_html(base: Path | None = None) -> Path:
    """Pages de la section infra. HTML seul : pas de jumeau markdown."""
    return (base or racine()) / "docs/infra"


def chapitres_infra(base: Path | None = None) -> list[Path]:
    """Chapitres infra numérotés, dans l'ordre. Exclut index.html."""
    return sorted(infra_html(base).glob("[0-9][0-9]-*.html"))


# ── Ancres ──────────────────────────────────────────────────────────────────


def ancre(titre: str) -> str:
    """Transforme un titre en ancre, à la manière de GitHub.

    ⚠️ Deux pièges, tous deux rencontrés pour de vrai :

    - GitHub met **un tiret par espace**. « A : B » donne ``a--b``, avec deux
      tirets, parce que « : » disparaît en laissant ses deux espaces. Fusionner
      les espaces produit de faux positifs en masse.
    - Le tiret **final** est conservé : « Et le format ? » donne ``et-le-format-``.

    Les accents sont gardés (``\\w`` avec le drapeau Unicode).
    """
    texte = re.sub(r"`|\*\*|<[^>]+>", "", titre).strip().lower()
    texte = re.sub(r"[^\w \-]", "", texte, flags=re.UNICODE)
    return texte.replace(" ", "-")


def ancres_md(contenu: str) -> set[str]:
    """Ancres offertes par un document markdown."""
    return {ancre(t) for t in re.findall(r"^#{1,6} +(.+)$", contenu, re.M)}


def ancres_html(contenu: str) -> set[str]:
    """Ancres offertes par une page HTML (tout attribut ``id``)."""
    return set(re.findall(r'id="([^"]+)"', contenu))


# ── Divers ──────────────────────────────────────────────────────────────────


def liens_html(contenu: str) -> list[str]:
    """``href`` internes seulement.

    ⚠️ Le favicon du site est une URI ``data:`` contenant un SVG avec ses propres
    guillemets et un ``#``. Sans ce filtre, chaque page produit un faux positif.
    """
    return [
        h
        for h in re.findall(r'href="([^"]+)"', contenu)
        if not h.startswith(("http://", "https://", "mailto:", "data:", "#!"))
    ]


def titre_de(page: Path) -> str:
    """Titre affiché d'un chapitre (``<h1>`` ou ``# ``), sans son numéro."""
    contenu = page.read_text()
    if page.suffix == ".html":
        m = re.search(r"<h1>(?:\d+\.\s*)?(.+?)</h1>", contenu, re.S)
    else:
        m = re.search(r"^# (?:\d+\.\s*)?(.+)$", contenu, re.M)
    return m.group(1).strip() if m else page.stem


ROUGE, VERT, JAUNE, GRIS, RAZ = "\033[31m", "\033[32m", "\033[33m", "\033[90m", "\033[0m"
