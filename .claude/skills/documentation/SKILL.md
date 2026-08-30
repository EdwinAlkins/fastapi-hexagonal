---
name: documentation
description: Travailler sur la documentation de ce dépôt — le cours (markdown dans backend/docs/cours/ et site HTML dans docs/), la section infra, la landing page. Contient les scripts de vérification (liens, ancres, parité md/html, navigation, comptages), de renumérotation de chapitres et de création de chapitre. À charger avant toute modification du cours, du site ou des README, et notamment pour ajouter/déplacer/renommer un chapitre.
---

# Documentation du dépôt

## Ce qui existe, et où

| Quoi | Où | Lu depuis |
|---|---|---|
| Cours, source markdown | `backend/docs/cours/NN-slug.md` | GitHub |
| Cours, site | `docs/cours/NN-slug.html` | GitHub Pages |
| Section infra | `docs/infra/NN-slug.html` | GitHub Pages (pas de markdown) |
| Landing | `docs/index.html` | GitHub Pages |
| Carnet DDD stratégique | `backend/docs/ddd-strategique-terrain.md` + `docs/cours/ddd-strategique.html` | les deux |
| Feuille de style unique | `docs/assets/style.css` | — |
| Publication | `.github/workflows/pages.yml`, `docs/.nojekyll` | — |

**Les deux versions du cours sont écrites à la main, séparément.** Il n'y a pas de
générateur markdown → HTML et il ne faut pas en fabriquer un : une tentative de
conversion semi-automatique a déjà tourné en boucle infinie. `verifier.py` garantit
qu'elles restent en correspondance ; c'est le filet, pas un pont.

## Les scripts

Tous dans `scripts/`, sans dépendance hors bibliothèque standard, exécutables
depuis n'importe quel répertoire du dépôt.

```bash
S=.claude/skills/documentation/scripts

python3 $S/verifier.py                  # tout
python3 $S/verifier.py liens parite     # une ou plusieurs familles
python3 $S/aligner_ancres.py            # écart md/html sur les id (--ecrire pour appliquer)
python3 $S/renumeroter.py 10            # libère le numéro 10 (--fermer pour l'inverse, --ecrire)
python3 $S/squelette.py 10 mon-slug "Mon titre" "Court" --ecrire
```

`verifier.py` sort en code non nul dès qu'un contrôle échoue. Cinq familles :

- **structure** — balises équilibrées, `id` uniques, toute classe existe dans
  `style.css`, `<title>` présent, saut de ligne final, `aria-current="page"` sur
  chaque page de contenu ;
- **liens** — cibles et ancres, côté HTML **et** côté markdown ;
- **parite** — mêmes chapitres et mêmes sections des deux côtés (cours seulement :
  la section infra n'a pas de jumeau markdown) ;
- **navigation** — sidenav complet sur chaque page, chaîne des pagers continue,
  **pour le cours ET pour l'infra**. Le dernier chapitre infra retourne à
  `index.html` au lieu d'enchaîner : cette exception est contrôlée à part ;
- **comptages** — le nombre de chapitres est affirmé à plusieurs endroits (deux
  README, deux index, la méta-description), ils doivent concorder ; le sommaire
  `docs/infra/index.html` doit lister exactement les chapitres infra présents.

**Lance `verifier.py` avant de dire que c'est fini.** Il attrape précisément ce
qu'une relecture humaine laisse passer.

## La règle d'ancrage, qui a coûté deux erreurs

GitHub met **un tiret par espace**, et ne fusionne pas. « `A : B` » donne `a--b`
(deux tirets : le « : » disparaît en laissant ses deux espaces). Le tiret **final**
est conservé : « Et le format ? » → `et-le-format-`. Les accents restent.

Un vérificateur qui fusionne les espaces produit des faux positifs en masse — c'est
arrivé, sur six ancres pourtant valides. La règle vit une seule fois, dans
`commun.ancre()` : ne la réimplémente pas ailleurs.

Autre piège du même genre : le favicon du site est une URI `data:` contenant un SVG
avec ses propres guillemets et un `#`. Tout vérificateur de liens doit filtrer
`data:` — sinon chaque page produit un faux positif. C'est fait dans
`commun.liens_html()`.

## Écrire

- **Français**, tutoiement, sans jargon inutile. Ton du cours : affirmatif, on
  justifie les choix et on nomme les compromis plutôt que de les taire.
- **Chaque chapitre** : `# NN. Titre`, un `> **TL;DR** —`, le corps, `## À retenir`,
  `## À toi de jouer` (2 à 4 exercices), et le lien vers les corrigés.
- **Aucun chiffre inventé.** Toute mesure, taille de fichier, durée ou nombre de
  tests se vérifie dans le code avant d'être écrite. Un « ~3 min » et un « 80
  lignes » plausibles se sont révélés faux ; un « 64 tests » aussi, alors que
  `pytest --collect-only` en annonçait 72.
- **Les estimations de temps de lecture par chapitre ont été retirées volontairement.**
  Ne pas les réintroduire.

### Le vocabulaire HTML disponible

Classes définies dans `style.css` — `verifier.py` refuse toute classe inconnue :

*Contenu d'un chapitre* — `note` (encadré neutre) · `warn` (attention) · `danger` ·
`tldr` · `snippet` (avec `data-lang`) · `table-wrap` (obligatoire autour de chaque
`<table>`) · `table-principe` · `exercises` · `solutions` · `anchor` · `lede`.

*Charpente de page* — `shell` · `sidenav` · `pager` · `topbar` · `topnav` ·
`brand` · `repo` · `site` · `skip` · `num` · `title` · `hook` · `toc`.

*Landing et infra* — `hero` · `landing` · `cards` · `cta` · `primary` · `diagram` ·
`closing` · `pill` · `pill-ok` · `pill-danger`.

Un encadré s'écrit `<div class="warn"><strong>Titre</strong><p>…</p></div>` — il
n'existe pas de `callout`, j'ai essayé.

Les blocs de code doivent échapper `<` et `>` : un `<horodatage>` non échappé casse
l'analyse de la page entière, en silence.

## Recettes

### Ajouter un chapitre

```bash
python3 $S/renumeroter.py 10 --ecrire          # si le numéro est pris
python3 $S/squelette.py 10 mon-slug "Titre long" "Titre court" --ecrire
```

Puis, à la main — `verifier.py` les listera tous :

1. le contenu, dans les **deux** versions ;
2. les listes de chapitres de `docs/index.html` et `docs/cours/index.html` ;
3. le tableau de `backend/docs/cours/README.md` (sa colonne de numéros est
   **séparée** du lien : un décalage ne la touche pas) ;
4. les comptages : `README.md` (chiffre et « chapitres 00 → NN ») et
   `docs/index.html` (méta-description **et** le nombre en toutes lettres) ;
5. la section « Chapitre NN » des corrigés d'annexes ;
6. le groupe (`<h2>`) du sidenav où l'entrée a atterri.

### Toucher aux annexes

`14-annexes` contient **trois** structures qu'on confond facilement :

- le tableau A « principe vs choix », à **4 colonnes** ;
- le glossaire, à **3 colonnes** ;
- les corrigés, en sections `#chapitre-NN`.

Six termes figurent dans le tableau **et** le glossaire — « Agrégat », « Composition
root », « DTO », « Entité », « Repository », « Value object » : un remplacement sur
la première occurrence vise le tableau. Vérifie toujours dans laquelle tu écris — une ligne à 3 colonnes
insérée dans le tableau à 4 passe inaperçue à la relecture.

Et **le glossaire est déjà fourni** : cherche le terme avant d'en ajouter un.
« Idempotence » et « Unit of Work » y étaient déjà quand j'ai voulu les créer.

### Renommer une section

Le titre change dans le markdown → l'`id` HTML doit suivre, et tout lien entrant
aussi. `aligner_ancres.py` s'occupe des `id` et de leur auto-lien ; `verifier.py`
signale ensuite les liens entrants devenus faux.

### Publier une mesure

Écris un test jetable dans `backend/tests/integration/`, lance-le, note le chiffre,
**puis supprime le fichier**. Ce qui reste dans le dépôt, c'est un test qui verrouille
la propriété (« exactement 1 SELECT »), pas le banc de mesure.

## Deux duplications à surveiller

- **Le sidenav est recopié dans chaque page.** Toute modification est un balayage.
  L'oublier sur une seule page ne se voit qu'à l'œil — c'est arrivé, et c'est
  l'utilisateur qui l'a vu, pas moi. `verifier.py navigation` couvre ce cas, dans
  les deux sections. Il a d'ailleurs trouvé, dès son extension à l'infra, un pager
  de `01-donnees` qui remontait au sommaire au lieu du chapitre précédent.
- **La landing reprend des schémas des pages de chapitre.** Ils divergent
  silencieusement. Après modification d'un schéma, compare les deux copies octet
  à octet.
