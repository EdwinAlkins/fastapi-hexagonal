# Cours — Architecture hexagonale & DDD en pratique

Un cours progressif pour **comprendre les concepts** qui structurent ce projet,
et surtout pouvoir les **réutiliser ailleurs** — dans un autre langage, un autre
framework, un autre métier.

Ce n'est pas un manuel théorique : chaque notion est illustrée par le **code réel
de ce dépôt** (un gestionnaire de tâches avec deux contextes, `task` et `user`,
liés par une relation 1→n, une API HTTP, un CLI et un worker RabbitMQ).

## À qui s'adresse ce cours

À un développeur qui sait coder mais veut comprendre **pourquoi** organiser une
application de cette manière, et **comment** raisonner pour la concevoir soi-même.

**Prérequis** : Python (classes, `async`/`await`, type hints), les bases d'un ORM
et d'une API HTTP. Aucune connaissance préalable de DDD n'est nécessaire.

## Comment lire ce cours

Les chapitres sont progressifs — chacun s'appuie sur le précédent. Les
chapitres 3 et 5 sont les plus denses.

| # | Chapitre | Ce que tu y gagnes |
|---|----------|--------------------|
| 00 | [Le problème](00-le-probleme.md) | Pourquoi cette architecture existe, avant/après |
| 01 | [La règle de dépendance](01-regle-de-dependance.md) | La seule règle qui compte, et comment la vérifier |
| 02 | [Où vit une règle ?](02-ou-vit-une-regle.md) | L'arbre de décision central du cours |
| 03 | [Le domaine](03-le-domaine.md) | DDD stratégique, value objects, entités, invariants |
| 04 | [Les agrégats](04-les-agregats.md) | Frontière de cohérence, racine, comment la choisir |
| 05 | [Relations entre agrégats](05-relations-entre-agregats.md) | Référence par identité, cardinalités, N+1 |
| 06 | [Application & ports](06-application-et-ports.md) | Use cases, DTO, où placer un port |
| 07 | [Les adaptateurs](07-adaptateurs.md) | ORM, mappers, HTTP, CLI, worker |
| 08 | [Transactions & erreurs](08-transactions-et-erreurs.md) | Frontière transactionnelle, erreurs métier vs techniques, DI |
| 09 | [Lire sans passer par le domaine](09-lectures-et-query-services.md) | Query services, N+1, CQRS léger |
| 10 | [Écrire en masse](10-ecritures-en-masse.md) | Reconstitution, bulk writers, idempotence, `UnitOfWork` |
| 11 | [Cache & événements](11-cache-et-evenements.md) | Cache-aside, événements de domaine vs d'intégration |
| 12 | [Organisation & tests](12-organisation-et-tests.md) | Tranches verticales, les trois niveaux de tests |
| 13 | [Démarrer un projet](13-demarrer-un-projet.md) | La recette, la checklist, et quand *ne pas* l'appliquer |
| 14 | [Annexes](14-annexes.md) | Concept vs notre choix, glossaire, corrigés, bibliographie |

## L'idée en une phrase

> Le **cœur métier** de l'application ne doit dépendre d'**aucun détail
> technique** (base de données, framework web, format JSON). Les détails se
> branchent *sur* le cœur, jamais l'inverse.

Tout le reste découle de ça.

## Une convention importante : principe ≠ notre choix

Beaucoup de cours d'architecture présentent les choix de leur auteur comme des
lois universelles. C'est le piège le plus courant, et il produit des développeurs
dogmatiques. Ici, chaque fois qu'un choix d'implémentation est discutable, tu
trouveras un encadré à trois colonnes :

| Concept | Ce que dit le principe | Ce que fait ce projet |
|---------|------------------------|-----------------------|
| Value object | Pas d'identité, égalité par valeur | `dataclass(frozen=True, slots=True)`, auto-validé |

La colonne du milieu est transférable partout. La colonne de droite est **un**
choix parmi d'autres, valide dans **ce** contexte. Savoir les distinguer, c'est
la différence entre appliquer une recette et concevoir une architecture.

Le tableau complet de ces distinctions est regroupé en [annexe](14-annexes.md#a-principe-vs-choix-de-ce-projet).

## Vocabulaire de base (à garder sous la main)

| Terme | Définition courte |
|-------|-------------------|
| **Domaine** | Le cœur métier : les règles, indépendantes de toute technique. |
| **Port** | Une interface exprimant un *besoin* du cœur (ce dont il a besoin). |
| **Adaptateur** | Une implémentation concrète d'un port (ce qui *fournit* le besoin). |
| **Driving / driven** | Adaptateur qui *pilote* l'app (API, CLI, worker) vs. qui est *piloté* par elle (BDD, cache, SMTP). |
| **Entité** | Objet métier avec une identité stable dans le temps (`Task`, `User`). |
| **Value object** | Objet défini par sa valeur, sans identité propre (`Email`, `TaskTitle`). |
| **Agrégat** | Une frontière de cohérence transactionnelle, avec une racine. |
| **Use case** | Une action applicative qui orchestre le domaine (`CreateTask`). |
| **Bounded context** | Une frontière métier autonome, avec son vocabulaire (`task`, `user`). |

Le [glossaire complet](14-annexes.md#b-glossaire) est en annexe.

## À toi de jouer

Chaque chapitre se termine par deux ou trois exercices courts. Ils ne demandent
pas d'écrire beaucoup de code — surtout de **décider où placer quelque chose**,
qui est la compétence réelle que ce cours essaie de transmettre. Les corrigés
sont en [annexe](14-annexes.md#c-corrigés-des-exercices).
