# 13. Démarrer un nouveau projet

> **TL;DR** — Pars du cœur vers l'extérieur. Vérifie la checklist. Et surtout :
> sache reconnaître les projets où **rien de tout ça** n'est justifié.

Ce chapitre transforme les concepts en recette. Il est volontairement agnostique :
les principes valent en Python, Java, C#, TypeScript, Go.

## La recette, couche par couche

Commencer par le cœur est contre-intuitif — on veut souvent partir de la base ou
de l'API. C'est justement ce qui garde le domaine pur : tout ce que tu écris
avant d'avoir une base de données est, par construction, indépendant d'elle.

### Étape 0 — Le langage avant le code

Avant tout fichier, écris la liste des **noms du métier** et leur définition :
qu'est-ce qu'une « tâche » ? Qu'est-ce que « terminer » veut dire exactement ?
Qui a le droit de le faire ? Si tu ne sais pas répondre, aucune architecture ne
te sauvera.

C'est aussi ici que tu cherches les **bounded contexts** — des frontières à
l'intérieur desquelles un modèle et son langage restent cohérents
([ch. 03](03-le-domaine.md#bounded-context--une-frontière-de-sens)). L'indice le
plus visible est le vocabulaire : un « utilisateur » au sens authentification
(identifiants, sessions, rôles) n'est pas le même concept qu'un « utilisateur » au
sens métier (propriétaire de tâches), même s'ils partagent un identifiant. Un mot
qui recouvre deux concepts est un signal fort — mais c'est la cohérence du
*modèle* qui tranche, pas le lexique seul.

### Étape 1 — Le domaine (aucune dépendance technique)

1. Identifie les **value objects** : concepts définis par leur valeur, avec leurs
   règles de validité (`Email`, `Money`, `TaskTitle`). Auto-validés à la
   construction.
2. Identifie les **entités** et **agrégats** : les concepts avec une identité, et
   surtout **les frontières de cohérence transactionnelle** ([ch. 04](04-les-agregats.md)).
   Exprime les invariants en méthodes (`order.confirm()`, pas `order.status = ...`).
3. Écris les **exceptions métier**, hiérarchisées par sémantique (`NotFound`,
   `Conflict`, `Validation`).
4. Déclare les **ports de persistance** dont le modèle a besoin.

✅ Vérifie : le domaine s'importe-t-il sans aucun framework ? Ses tests unitaires
tournent-ils en millisecondes ? Écris-les **maintenant**, pas plus tard.

### Étape 2 — L'application (dépend du domaine seul)

5. Un **use case** par action (`CreateOrder`, `CancelOrder`). Il reçoit des ports,
   orchestre, ne porte pas les invariants.
6. Des **DTO** neutres en entrée (commandes) et en sortie.
7. Les **ports techniques** dont les cas d'usage ont besoin (cache, notification,
   publication) — dans `application/`, pas dans le domaine
   ([ch. 06](06-application-et-ports.md)).

### Étape 3 — Les adaptateurs

8. **Persistance** : modèles ORM (distincts des entités), **mappers**, et
   l'implémentation concrète des ports. Les repositories ne committent pas et
   reçoivent leur session.
9. **Entrée** : schémas de transport, routers/commandes/consumers qui traduisent,
   et rien d'autre.

### Étape 4 — Le câblage transverse

10. La **frontière transactionnelle**, fournie par chaque adaptateur entrant.
11. La traduction **erreurs métier / erreurs techniques → protocole**.
12. La **composition root** qui relie ports et adaptateurs.
13. Les **tests d'intégration** de bout en bout, sur les moteurs réels.

### Étape 5 — Les garde-fous, tout de suite

14. Le **contrôle automatique de la règle de dépendance** (import-linter ou
    équivalent), en CI dès le premier jour. Ajouté après six mois, il ne passe
    jamais du premier coup.

## Squelette de démarrage

```bash
mkdir -p src/monprojet/domain/{shared,mon_contexte}
mkdir -p src/monprojet/application/{shared,mon_contexte}
mkdir -p src/monprojet/infrastructure/persistence/mon_contexte
mkdir -p src/monprojet/presentation/api/v1/{routers,schemas}
mkdir -p tests/{unit/domain,unit/application,integration}
```

Dans ce dépôt, le contexte **`user`** est la référence complète : domaine,
application, persistance, DI, schémas, routers, tests aux trois niveaux. Pour un
use case seul, `RenameUser` est l'exemple minimal (mutation + invalidation de
cache).

## Checklist de revue

Avant de dire « c'est propre » :

- [ ] Le contrôle d'architecture passe (`make imports`) — pas juste un `grep`.
- [ ] Les entités changent d'état par **méthodes**, jamais par attributs nus.
- [ ] Les value objects valident **une forme**, sans I/O.
- [ ] Chaque agrégat a une **frontière justifiable** : quel invariant la motive ?
- [ ] Les agrégats se référencent **par identité** ; à l'intérieur, les objets se
      référencent normalement.
- [ ] Les repositories **ne committent pas** ; la transaction entoure le use case.
- [ ] Le domaine lève des **exceptions métier** ; les erreurs techniques ont leur
      hiérarchie et leur code (5xx).
- [ ] Aucun `HTTPException`, aucun logger, aucun framework dans le domaine.
- [ ] Les use cases sont testables **sans** base ni HTTP (doublures en mémoire).
- [ ] Chaque port est dans la couche qui **exprime le besoin**.
- [ ] Tout cache a un **contrat d'invalidation écrit**.
- [ ] Un nouveau contexte = de **nouveaux fichiers**, pas des modifications
      dispersées.

## Les pièges les plus fréquents

- **Modèle anémique** : des entités sans comportement, toute la logique dans les
  use cases (ou pire, dans les routers). Le domaine n'existe alors pas vraiment.
- **Fusionner entité et modèle ORM** : le domaine se met à dépendre de l'ORM.
- **Committer dans le repository** : casse l'atomicité multi-écritures.
- **Naviguer entre agrégats** (`user.tasks`) au lieu de requêter par identité.
- **Croire que le DDD interdit les collections** : à l'intérieur d'un agrégat,
  elles sont normales ([ch. 04](04-les-agregats.md)).
- **Tout mettre dans des services** : c'est le modèle anémique déguisé.
- **Ranger toutes les erreurs sous `DomainError`** : une panne de broker n'est pas
  un problème métier.
- **Confondre query service et CQRS** ([ch. 09](09-lectures-et-query-services.md#et-cqrs-alors-)).
- **Sur-découper** : appliquer un pattern (façade, sous-dossiers) partout par
  réflexe. Le découpage doit servir la lisibilité, cas par cas.
- **Attendre pour automatiser la règle de dépendance.**

## Quand NE PAS utiliser cette architecture

Elle a un coût réel — plus de fichiers, des mappers, de l'indirection — qui se
rentabilise quand le **métier est riche** et la **durée de vie longue**. Les
signaux qu'elle est surdimensionnée :

- **Un CRUD sans règles.** Si le seul invariant est « ce champ est obligatoire »,
  tes entités seront des DTO avec un mapper — pure cérémonie.
- **Un prototype jetable**, un script, un one-shot d'analyse.
- **Une équipe d'une personne sur trois mois**, sur un besoin qui ne durera pas.
- **Un service dont le vrai travail est ailleurs** : un proxy, un ETL, un
  transformateur de fichiers. Leur complexité est technique, pas métier — cette
  architecture protège le métier d'une complexité qu'ils n'ont pas.

Dans ces cas : FastAPI + Pydantic + un ORM à plat suffisent, et sont **plus
lisibles**. Savoir ne pas appliquer un pattern fait partie de sa maîtrise.

### Et l'entre-deux ?

C'est le cas le plus fréquent, et il n'oblige pas à choisir en bloc. Ces éléments
se prennent séparément, par ordre de rapport bénéfice/coût :

1. **Des value objects auto-validés** — quasiment gratuits, bénéfice immédiat.
2. **Des règles dans les entités** plutôt que dans les routers — gratuit aussi.
3. **Des use cases** appelables hors HTTP — le jour où un CLI ou un cron arrive.
4. **Des ports et des mappers** — le plus coûteux ; à prendre quand la
   substituabilité ou la testabilité sans I/O devient un vrai besoin.

Beaucoup de projets gagnent énormément aux niveaux 1 et 2, et n'ont jamais besoin
du 4.

## Pour aller plus loin

- **Domain-Driven Design** (Eric Evans) — le livre fondateur. Le DDD stratégique
  (première partie) est plus important que les patterns tactiques, et bien moins lu.
- **Implementing Domain-Driven Design** (Vaughn Vernon) — plus pratique ; c'est de
  là que vient « référencer les agrégats par identité ».
- **Hexagonal Architecture** (Alistair Cockburn, 2005) — l'article d'origine des
  ports & adapters, court et toujours pertinent.
- **Clean Architecture** (Robert C. Martin) — la règle de dépendance formalisée,
  et l'origine du découpage en quatre couches utilisé ici.
- **Patterns of Enterprise Application Architecture** (Martin Fowler) — les
  définitions de référence de *Repository*, *Unit of Work*, *Data Mapper*.
- **Architecture Patterns with Python** (Percival & Gregory) — le plus proche de ce
  projet : Python, ports & adapters, Unit of Work, événements. Lisible en ligne.

## Le mot de la fin

Ne récite pas les patterns. Ce cours tient en deux questions à te poser en
permanence :

> **Cette décision, à qui appartient-elle ?**
> **Qu'est-ce qui doit être cohérent au sein d'une même transaction ?**

Ports, mappers, DTO, composition root ne sont que la machinerie qui rend les
réponses exécutables. Si un choix protège l'isolation du cœur métier tout en
gardant le code lisible, il est probablement bon — même s'il ne suit aucun
pattern nommé. Et s'il suit tous les patterns nommés sans que personne ne sache
dire quel problème il résout, il est probablement mauvais.

## À toi de jouer

1. Un service qui reçoit des webhooks Stripe, les valide et les range en base.
   Combien de niveaux de la liste « entre-deux » lui appliquerais-tu ?
2. Pour un e-commerce, propose trois bounded contexts et cite un mot qui n'a pas
   le même sens dans deux d'entre eux.
3. Reprends la checklist et applique-la à un projet que tu connais. Quel point
   échoue en premier, et quel serait le correctif le moins coûteux ?

→ [Corrigés](14-annexes.md#c-corrigés-des-exercices)
