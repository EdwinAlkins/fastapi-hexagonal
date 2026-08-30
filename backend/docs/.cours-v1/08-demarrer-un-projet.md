# 8. Démarrer un nouveau projet

Ce chapitre transforme les concepts en **recette**. Il est volontairement
agnostique : les principes valent en Python, Java, C#, TypeScript…

## La recette, couche par couche

Pars **du cœur** vers l'extérieur. C'est contre-intuitif (on veut souvent
commencer par la base ou l'API), mais c'est ce qui garde le domaine pur.

### Étape 1 — Le domaine (aucune dépendance technique)

1. Identifie les **value objects** : les concepts définis par leur valeur, avec
   leurs règles de validité (`Email`, `Money`, `TaskTitle`). Immuables, auto-validés.
2. Identifie les **entités / agrégats** : les concepts avec une identité, et
   leurs **invariants** exprimés en méthodes (`order.confirm()`, pas `order.status = ...`).
3. Écris les **exceptions métier**, hiérarchisées par sémantique
   (`NotFound`, `Conflict`, `Validation`).
4. Déclare les **ports** (interfaces de repository) dont le domaine a besoin.

✅ Vérifie : le domaine ne compile-t-il sans aucun framework ? Écris déjà ses
tests unitaires.

### Étape 2 — L'application (dépend du domaine seul)

5. Un **use case** par action (`CreateOrder`, `CancelOrder`…). Il reçoit des
   ports, orchestre, ne contient pas de règle.
6. Des **DTO** neutres en entrée (commands) et sortie.

### Étape 3 — Les adaptateurs (dépendent du domaine)

7. **Persistance** : modèles ORM (distincts des entités), **mappers**, et
   l'implémentation concrète des ports. Les repositories ne committent pas.
8. **API** : schémas de transport, routers qui traduisent HTTP ↔ use cases,
   traduction des exceptions métier → statuts.

### Étape 4 — Le câblage transverse

9. La **frontière transactionnelle** (commit/rollback à la requête).
10. La **composition root** qui relie ports → adaptateurs.
11. Les **tests d'intégration** de bout en bout.

## Checklist de revue

Avant de dire « c'est propre », vérifie :

- [ ] `grep` framework dans le domaine → **vide**.
- [ ] Les entités changent d'état par **méthodes**, jamais par attributs nus.
- [ ] Les value objects sont **immuables** et validés à la construction.
- [ ] Les agrégats se référencent **par identité** (ID), pas par objet.
- [ ] Les repositories **ne committent pas** ; la transaction est à la requête.
- [ ] Le domaine lève des **exceptions métier**, jamais de code HTTP.
- [ ] Les use cases sont testables **sans** base ni HTTP.
- [ ] Un nouveau contexte = de **nouveaux fichiers**, pas des modifs partout.

## Les pièges les plus fréquents

- **Modèle anémique** : des entités sans comportement, toute la logique dans les
  use cases (ou pire, dans les routers). Signe que le domaine n'existe pas vraiment.
- **Fusionner entité et modèle ORM** : le domaine se met à dépendre de l'ORM.
- **Committer dans le repository** : casse l'atomicité multi-écritures.
- **Naviguer entre agrégats** (`user.tasks`) au lieu de requêter par identité.
- **Laisser Pydantic/HTTP fuiter dans le domaine** pour « gagner du temps ».
- **Sur-découper** : appliquer un pattern (façade, sous-dossiers) partout par
  réflexe. Le découpage doit servir la lisibilité, cas par cas.

## Quand NE PAS utiliser cette architecture

Elle a un coût (plus de fichiers, mappers, indirection). Elle se rentabilise
quand le **métier est riche** et la **durée de vie longue**. Pour :

- un **CRUD simple** sans vraie logique métier,
- un **prototype jetable** ou un script,
- une équipe qui n'a pas besoin de swapper d'adaptateurs,

… c'est probablement **du sur-dimensionnement**. Un FastAPI + Pydantic + ORM à
plat suffit. Savoir *ne pas* l'appliquer fait partie de la maîtrise.

## Pour aller plus loin

Les idées de ce cours viennent surtout de :

- **Domain-Driven Design** (Eric Evans) — le livre fondateur (DDD stratégique et tactique).
- **Implementing Domain-Driven Design** (Vaughn Vernon) — plus pratique ; d'où vient « référencer les agrégats par identité ».
- **Hexagonal Architecture** (Alistair Cockburn) — l'article d'origine des ports & adapters.
- **Clean Architecture** (Robert C. Martin) — la règle de dépendance formalisée.
- **CQRS** — la séparation lecture/écriture évoquée au chapitre 5.

## Le mot de la fin

Ne récite pas les patterns : **comprends la règle de dépendance**. Tout le reste
(ports, mappers, DTO, composition root) n'est qu'une façon de la faire respecter.
Si un choix protège l'isolation du cœur métier tout en gardant le code lisible,
il est probablement bon — même s'il ne « suit » aucun pattern nommé.
