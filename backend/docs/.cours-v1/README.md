# Cours — Architecture hexagonale & DDD en pratique

Un cours court et concret pour **comprendre les concepts** qui structurent ce
projet, et surtout pouvoir les **réutiliser sur d'autres projets** (quel que
soit le langage ou le framework).

Il ne s'agit pas d'un manuel théorique : chaque notion est illustrée par le
code réel de ce dépôt (un gestionnaire de tâches avec deux contextes, `task` et
`user`, liés par une relation 1→n).

## À qui s'adresse ce cours

À un développeur qui sait coder mais veut comprendre **pourquoi** organiser une
application de cette manière, et **comment** reproduire l'exercice ailleurs.

## Comment le lire

Les chapitres sont progressifs — chacun s'appuie sur le précédent. Comptez ~10
min par chapitre.

1. [Architecture hexagonale](01-architecture-hexagonale.md) — la seule règle qui compte : la *règle de dépendance*.
2. [Le domaine (DDD tactique)](02-le-domaine.md) — value objects, entités, agrégats, invariants.
3. [Application & use cases](03-application-use-cases.md) — ports, orchestration, DTO.
4. [Les adaptateurs](04-adaptateurs.md) — persistance (ORM) et API (HTTP) branchés sur le cœur.
5. [Relations entre agrégats](05-relations-entre-agregats.md) — modéliser les relations (1→n, n→1, 1↔1, n↔n) proprement.
6. [Décisions transverses](06-decisions-transverses.md) — erreurs, transactions, injection de dépendances.
7. [Organisation & tests](07-organisation-et-tests.md) — tranches verticales, pyramide de tests.
8. [Démarrer un nouveau projet](08-demarrer-un-projet.md) — la recette, la checklist, et quand *ne pas* utiliser tout ça.

## L'idée en une phrase

> Le **cœur métier** de l'application ne doit dépendre d'**aucun détail
> technique** (base de données, framework web, format JSON). Les détails se
> branchent *sur* le cœur, jamais l'inverse.

Tout le reste découle de ça.

## Le vocabulaire de base (à garder sous la main)

| Terme | Définition courte |
|-------|-------------------|
| **Domaine** | Le cœur métier : les règles, indépendantes de toute technique. |
| **Port** | Une interface définie par le domaine (ce dont il a *besoin*). |
| **Adaptateur** | Une implémentation concrète d'un port (ce qui *fournit* le besoin). |
| **Driving / driven** | Adaptateur qui *pilote* l'app (API) vs. qui est *piloté* par elle (BDD). |
| **Entité** | Objet métier avec une identité stable dans le temps (`Task`, `User`). |
| **Value object** | Objet défini par sa valeur, immuable, auto-validé (`Email`, `TaskTitle`). |
| **Agrégat** | Un groupe d'objets traité comme une unité de cohérence, avec une racine. |
| **Use case** | Une action applicative qui orchestre le domaine (`CreateTask`). |
| **Bounded context** | Une frontière métier autonome (`task`, `user`). |
