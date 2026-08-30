# 14. Annexes

- [A. Principe vs choix de ce projet](#a-principe-vs-choix-de-ce-projet)
- [B. Glossaire](#b-glossaire)
- [C. Corrigés des exercices](#c-corrigés-des-exercices)

---

## A. Principe vs choix de ce projet

Le tableau le plus important du cours. La colonne du milieu est **transférable
partout** ; celle de droite est **un** choix valide dans **ce** contexte. Les
confondre est la première cause de dogmatisme.

| Concept | Ce que dit le principe | Ce que fait ce projet | Autres options courantes |
|---|---|---|---|
| **Bounded contexts** | Frontières où un modèle et son langage restent cohérents | `task` et `user`, couplés par le seul `UserId` | Contexte unique (monolithe modulaire naissant), services séparés + ACL |
| **Règle de dépendance** | Les dépendances pointent vers l'intérieur | 4 couches, vérifiées par import-linter | 2 zones (dedans/dehors), ArchUnit, tests d'archi maison |
| **Value object** | Pas d'identité, égalité par valeur | `dataclass(frozen=True, slots=True)`, auto-validé, normalisé | `NamedTuple`, `attrs`, classe classique |
| **Identité** | Générée par le domaine, opaque | `UUIDv7` via `uuid.uuid7()` | UUIDv4, ULID, séquence base (couplage) |
| **Entité** | Identité stable, égalité par id | Attributs publics, mutation par méthodes | Attributs `_privés` + `@property` |
| **Agrégat** | Frontière de cohérence : les invariants qui doivent rester vrais ensemble | `Task` et `User` séparés, référence par `UserId` | Agrégats plus gros si un invariant le justifie |
| **Portée transactionnelle** | 1 transaction = 1 agrégat (prépare la distribution) | 1 transaction = 1 use case | Saga / outbox si multi-service |
| **Port de persistance** | Appartient à qui exprime le besoin | `domain/<ctx>/repository.py` | Port en `application/` si le modèle n'en dépend pas |
| **Ports techniques** | Idem | `application/shared/` (cache, SMTP, broker) | `domain/` (à éviter), ou pas de port du tout |
| **Frontière transactionnelle** | Entoure l'unité de travail | Fournie par chaque adaptateur entrant | Unit of Work explicite, décorateur `@transactional` |
| **Repository** | Abstraction de la persistance des agrégats | Interface domaine + impl. SQLAlchemy, **sans commit** | Repository qui gère sa transaction (autre modèle) |
| **ORM** | Détail d'infrastructure | Modèle ORM séparé + mapper | Active Record (couple le domaine), ORM sur l'entité |
| **DTO** | Séparer les frontières | `dataclass(frozen=True, slots=True)` | Pydantic (fait entrer le framework), `TypedDict` |
| **Erreurs** | Métier ≠ technique | `DomainError` (4xx) / `InfrastructureError` (503) | `Result`/`Either` plutôt que des exceptions |
| **Écritures en masse** | Passent par les agrégats, comme toute écriture | `Task.reconstitute` + un **bulk writer** par contexte ; commit par lot via `UnitOfWorkPort` | `COPY` vers une table de transit |
| **Lectures** | Peuvent contourner les agrégats | Agrégats pour les listes simples ; un **query service** (`TaskQueryPort`) pour l'export joint tâche+propriétaire | CQRS léger, CQRS complet, Event Sourcing |
| **Événements** | Découplent ce qui se passe *après* | Événement d'**intégration** typé (`IntegrationEvent`) publié depuis le use case | Événements de **domaine** émis par l'agrégat |
| **Cache** | Optimisation, jamais source de vérité | Cache-aside, clé `user:{id}`, invalidation à la mutation | Write-through, TTL seul, pas de cache |
| **Composition root** | La décision d'association port ↔ adaptateur reste en un point unique | `presentation/api/dependencies/` + câblage manuel CLI/worker | Package `bootstrap/`, conteneur DI dédié |
| **Tests** | Le domaine doit se tester sans I/O | 3 niveaux : domaine / use cases (fakes) / intégration réelle | Mocks génériques, SQLite in-memory (déconseillé) |

---

## B. Glossaire

| Terme | Définition | Chapitre |
|---|---|---|
| **Adaptateur** | Implémentation concrète d'un port, ou point d'entrée qui pilote l'application. | [01](01-regle-de-dependance.md) |
| **Agrégat** | Groupe d'objets dont les invariants doivent rester vrais ensemble ; la transaction est le mécanisme habituel de cette cohérence, pas sa définition. | [04](04-les-agregats.md) |
| **Aggregate root** | Racine d'un agrégat : seule porte d'entrée, garante des invariants. | [04](04-les-agregats.md) |
| **Always-valid model** | Principe selon lequel un objet qui existe est nécessairement valide. | [03](03-le-domaine.md) |
| **Bounded context** | Frontière à l'intérieur de laquelle un modèle et son langage restent cohérents. | [03](03-le-domaine.md), [12](12-organisation-et-tests.md) |
| **Bulk writer** | Port d'écriture groupée : reçoit des agrégats déjà validés et n'optimise que leur transport vers la base. | [10](10-ecritures-en-masse.md) |
| **Composition root** | Point unique où se décide l'association port ↔ adaptateur. | [08](08-transactions-et-erreurs.md) |
| **Anti-corruption layer (ACL)** | Couche de traduction qui empêche le modèle d'un autre contexte de contaminer le tien. | [03](03-le-domaine.md) |
| **Context map** | Description des relations entre bounded contexts (shared kernel, conformist, ACL…). | [03](03-le-domaine.md) |
| **CQRS** | *Command Query Responsibility Segregation* : modèles de lecture et d'écriture séparés. | [09](09-lectures-et-query-services.md) |
| **DTO** | *Data Transfer Object* : structure neutre transportant des données entre couches. | [06](06-application-et-ports.md) |
| **Dual write** | Une opération qui écrit dans deux systèmes sans transaction commune ; aucun ordre n'est sûr. | [08](08-transactions-et-erreurs.md) |
| **Driving / driven** | Adaptateur qui pilote l'application (API, CLI, worker) / qui est piloté par elle (BDD, cache, SMTP). | [01](01-regle-de-dependance.md) |
| **Entité** | Objet métier à identité stable dans le temps ; égalité par identifiant. | [03](03-le-domaine.md) |
| **Événement de domaine** | Fait métier enregistré par un agrégat (`TaskCompleted`), interne au contexte. | [11](11-cache-et-evenements.md) |
| **Événement d'intégration** | Message publié vers l'extérieur, contrat public versionné. | [11](11-cache-et-evenements.md) |
| **Factory** | Point de construction d'un objet neuf dans un état initial cohérent (`Task.create`). | [03](03-le-domaine.md) |
| **Invariant** | Propriété qui doit rester vraie à tout instant de la vie d'un objet. | [02](02-ou-vit-une-regle.md), [03](03-le-domaine.md) |
| **Idempotence** | Propriété du *traitement* : le rejouer produit le même état qu'un seul passage. Obtenue à l'import par `ON CONFLICT DO NOTHING` sur des identités venues du fichier. | [08](08-transactions-et-erreurs.md) · [10](10-ecritures-en-masse.md) |
| **Inversion de dépendance** | Celui qui exprime le besoin possède l'interface ; l'implémentation lui obéit. | [01](01-regle-de-dependance.md) |
| **Langage ubiquitaire** | Vocabulaire partagé entre métier et code, utilisé littéralement dans le code. | [03](03-le-domaine.md) |
| **Mapper** | Traducteur entité ↔ modèle de persistance ; seul à connaître les deux formes. | [07](07-adaptateurs.md) |
| **Modèle anémique** | Objets sans comportement, logique reportée à l'extérieur — l'anti-pattern. | [03](03-le-domaine.md) |
| **N+1** | Une requête par élément d'une liste, faute de chargement explicite. | [05](05-relations-entre-agregats.md) |
| **Outbox** | Écrire le message à publier dans la même transaction que la donnée, puis le relayer ; fournit une publication *at-least-once*, jamais l'*exactly-once* à elle seule. | [08](08-transactions-et-erreurs.md), [11](11-cache-et-evenements.md) |
| **Policy applicative** | Règle propre à un cas d'usage (quota, plafond, pagination), non invariant du domaine. | [02](02-ou-vit-une-regle.md) |
| **Port** | Interface exprimant un besoin, déclarée par la couche qui l'exprime. | [06](06-application-et-ports.md) |
| **Reconstitution** | Reconstruction d'une entité **existante** dans son état, par opposition à sa création. Valide l'état, pas son atteignabilité. | [10](10-ecritures-en-masse.md) |
| **Query service** | Composant de lecture seule qui court-circuite les agrégats et renvoie des DTO à plat. | [09](09-lectures-et-query-services.md) |
| **Réification** | Transformer une relation porteuse de données en concept métier à part entière (`Enrollment`). | [05](05-relations-entre-agregats.md) |
| **Repository** | Port d'accès à la persistance d'un agrégat, exprimé en termes du domaine. | [06](06-application-et-ports.md) |
| **Saga** | Suite d'étapes locales avec une compensation par étape, quand aucune transaction commune n'existe. | [08](08-transactions-et-erreurs.md) |
| **Service de domaine** | Décision métier sans propriétaire naturel ; sans état, et sans I/O dans cette architecture. | [02](02-ou-vit-une-regle.md) |
| **Shared kernel** | Petit noyau de modèle partagé par deux contextes, modifié d'un commun accord. | [03](03-le-domaine.md) |
| **Unit of Work** | Regroupement des modifications validées d'un bloc. Réduit ici à un port exposant le seul **point d'acquisition** (`commit`), demandé explicitement par un use case long. | [08](08-transactions-et-erreurs.md) · [10](10-ecritures-en-masse.md) |
| **Use case** | Une action applicative, orchestrant le domaine via des ports. | [06](06-application-et-ports.md) |
| **Value object** | Objet sans identité propre, défini par sa valeur. | [03](03-le-domaine.md) |

---

## C. Corrigés des exercices

Ce ne sont pas des réponses uniques : plusieurs sont défendables. Ce qui compte
est le **critère** utilisé pour trancher.

### Chapitre 00

**1.** Le CLI (`task-manager-cli`) et le worker RabbitMQ (`NotifyTaskShared` charge
et manipule des tâches). Aucun ne passe par un router FastAPI : une validation
écrite dans le handler HTTP ne les protège pas. C'est la définition même d'une
règle sans domicile.

**2.** Le `commit` dans le handler valide la création **avant** que le débit de
quota n'ait lieu. Si le débit échoue ensuite, la tâche existe et le quota est
faux : les deux écritures ne sont plus atomiques. C'est exactement pourquoi la
frontière transactionnelle doit entourer le use case entier
([ch. 08](08-transactions-et-erreurs.md)).

### Chapitre 01

**1.** Ce n'est pas une violation. La règle interdit au domaine de dépendre de
**frameworks d'infrastructure** (web, ORM, sérialisation) — le contrat
`forbidden` de `pyproject.toml` liste précisément `fastapi`, `sqlalchemy`,
`pydantic`, `pydantic_settings`, `starlette`. `email_validator` est une
bibliothèque de règles **métier** (la forme d'un e-mail), sans I/O ici puisque
`check_deliverability=False`. La bonne question n'est pas « est-ce une dépendance
externe ? » mais « cette dépendance apporte-t-elle de la technique dans le cœur ? ».
Une dépendance pure et stable qui exprime une règle du métier est acceptable.

**2.** Le contrat `layers` : `application` se mettrait à importer
`infrastructure`, qui est au-dessus d'elle dans l'empilement. Ce qu'on perd
concrètement : impossible de tester un use case sans tirer SQLAlchemy, et surtout
la **direction de l'autorité** s'inverse — l'infrastructure dicterait la forme de
l'interface au lieu de la subir. Le jour où on veut un adaptateur non-SQL, c'est
le domaine qu'il faut renégocier.

### Chapitre 02

**1.a.** Dans le **use case** (`CreateTask`) : c'est une règle inter-agrégats,
donc de coordination.

**b.** `User` ne peut pas la porter : il faudrait compter les tâches, donc
interroger `TaskRepository` — une I/O, interdite dans une entité — et le contexte
`user` n'a de toute façon pas à connaître le contexte `task`. Faire porter la
règle par `Task` ne marche pas davantage : une tâche ne connaît pas ses sœurs.

**c.** Les deux requêtes lisent le compteur à 49, concluent toutes les deux que
c'est bon, et insèrent : on se retrouve à 51. C'est le classique *check-then-act*
sous concurrence — la vérification et l'écriture ne sont pas atomiques. La
fenêtre est petite mais réelle, et elle s'élargit avec la latence.

**d.** Plusieurs options, par ordre de coût croissant :
- un **verrou pessimiste** sur la ligne du user pendant la transaction
  (`SELECT … FOR UPDATE`), qui sérialise les créations d'un même propriétaire ;
- un **compteur dénormalisé** dans `users` avec une contrainte `CHECK
  (in_progress_count <= 50)`, incrémenté dans la même transaction — la base
  refuse alors structurellement le 51ᵉ ;
- un **index partiel unique** sur un numéro de slot, si le métier s'y prête.

Le schéma général est identique à l'unicité d'e-mail : le use case produit le
**message métier** lisible, la base produit la **garantie**. Une vérification
applicative sans garantie en base est un bug de concurrence en attente ; une
contrainte en base sans vérification applicative donne une erreur illisible.
Il faut les deux.

**2.** Dans `TaskTitle` (`TITLE_MAX_LENGTH`, avec `TitleTooLong`) et dans le
schéma HTTP (`Field(max_length=TITLE_MAX_LENGTH)`) — plus, en base, le
`String(200)` de `TaskModel`. Ce n'est pas une duplication fautive : ce sont
trois garde-fous à trois altitudes ([ch. 07](07-adaptateurs.md#deux-validations-deux-rôles-ne-pas-confondre)).
Le signe que c'est sain : la **constante est partagée**, pas recopiée. Le jour où
elle change, un seul endroit bouge (plus une migration).

**3.** Discutable, et c'est l'intérêt de la question. Le plafonnement est une
**policy applicative** : il protège le service, il n'est pas constitutif de ce
qu'est une tâche. Il vit donc dans le port et le use case (`limit=100` par
défaut, borné). La *valeur par défaut* affichée dans l'API peut, elle, être une
décision de présentation. Ce qu'il ne faut surtout pas, c'est laisser la
présentation passer un `limit` non borné jusqu'à la base.

### Chapitre 03

**1.** `dataclass` génère `__eq__` par valeur automatiquement — c'est exactement
le comportement voulu pour un value object. `Task`, elle, **redéfinit** `__eq__`
pour comparer par identité, parce que deux tâches de même titre ne sont pas la
même tâche. C'est la différence entité/VO rendue exécutable. (Et pour `Money`,
l'addition de deux devises différentes doit lever une exception métier, pas
convertir : le taux de change est un fait du monde extérieur, donc pas dans un VO.)

**2.** (a) Les tests deviennent dépendants du réseau et du DNS : lents, et rouges
au hasard en CI ou hors ligne. (b) Ils cessent d'être déterministes — un domaine
valide aujourd'hui peut devenir invalide demain sans qu'une ligne de code n'ait
changé. Plus grave : la classe `Email` n'est plus testable en isolation, ce qui
est précisément le signal du [chapitre 12](12-organisation-et-tests.md) qu'une
règle a été mélangée à de la technique.

**3.** La garde irait dans `Task.rename()`, à côté de celle de `complete()` :
c'est un invariant d'état d'un seul objet. **Surtout pas** dans le use case
`RenameTask` (elle serait contournable par le CLI ou le worker) ni dans le schéma
HTTP (qui ne connaît pas l'état actuel de la tâche).

### Chapitre 04

**1.a.** Deux agrégats, dans la quasi-totalité des cas. Invariant traversant ?
Aucun en général (« pas plus de N commentaires » est rare, et c'est plutôt une
policy de modération). Cycle de vie ? Les commentaires arrivent bien après la
publication, et peuvent être supprimés sans elle. Taille ? Non bornée.
Contention ? Deux commentaires simultanés se bloqueraient si l'article était la
racine.

**b.** Le critère décisif est la **taille non bornée** : c'est le seul des quatre
qui rend l'agrégat unique carrément impraticable, et pas seulement discutable.

**c.** Un article de type « tribune » limité à 3 réponses éditoriales, validées
avant publication et publiées avec elle. Là, l'invariant existe vraiment (« au
plus 3, et toutes validées »), le cycle de vie est commun, la taille est bornée :
l'agrégat unique devient le bon choix. Même modèle de données, conclusion
inverse — parce que le métier a changé, pas le schéma.

**d.** En choisissant deux agrégats, on accepte que le compteur de commentaires
affiché sur l'article soit une **lecture séparée** (requête ou compteur
dénormalisé), et donc potentiellement décalé d'un instant. C'est le compromis
normal : on échange une cohérence immédiate dont personne n'a besoin contre une
scalabilité dont tout le monde a besoin.

**2.** Deux agrégats. Le cas devient franc avec un prestataire externe : le
paiement a son propre cycle de vie, ses propres états (autorisé, capturé,
remboursé), et il **ne peut pas** être cohérent avec la commande dans la même
transaction — il arrive trois jours plus tard, par webhook. C'est le cas d'école
de la cohérence à terme : la commande passe en `PAID` en réaction à un événement,
pas dans la transaction qui l'a créée.

**3.** Il faudrait un invariant du type « un user ne peut pas être supprimé s'il
a des tâches en cours » **vérifié transactionnellement**, ou « la somme des
estimations de ses tâches ne dépasse pas son quota hebdomadaire ». Le second est
crédible dans un outil de gestion de charge. Mais même là, un agrégat unique est
un mauvais choix à cause du volume : la réponse habituelle est de maintenir un
compteur dénormalisé dans `User`, mis à jour dans la même transaction — ce qui est
un compromis, pas une frontière d'agrégat.

### Chapitre 05

**1.** `count_completed_by_owner` sur le port, ou un query service. Le critère est
le **volume transféré** : `list_by_owner` puis compte en Python charge N agrégats
complets pour produire un entier — inacceptable dès quelques centaines de tâches.
Entre les deux options restantes : une méthode de port si le compte reste dans le
contexte `task` et sert aussi à des décisions ; un query service dès qu'on
combine nom du user **et** compteur en un seul écran, puisqu'on traverse alors
deux contextes en lecture.

**2.** (a) Charger un user tirerait toutes ses tâches — non borné. (b) Le contexte
`user` dépendrait du contexte `task`, ce qu'aucune règle métier ne justifie. (c) En
SQLAlchemy async, l'accès paresseux lèverait une erreur à l'exécution, ou
imposerait un `selectinload` partout « au cas où ». Et un quatrième, plus
insidieux : le mapper `to_domain` de `user` devrait décider s'il charge les tâches
ou non, et une entité à moitié chargée est une bombe à retardement.

**3.** Parce qu'elle a une **identité propre et un cycle de vie** : on modifie une
inscription (attribuer une note), on l'annule, on l'historise. Deux inscriptions
avec les mêmes valeurs à un instant donné ne sont pas interchangeables. Et
`assign_grade` porte un invariant — un value object n'a pas d'invariant de
transition, il n'a pas de transitions du tout.

### Chapitre 06

**1.a.** Dans `application/shared/` — c'est déjà `SMTPSenderPort`.

**b.** Pas dans `domain/user/` parce qu'aucun invariant de `User` ne dépend de
l'envoi d'un e-mail : un user existe et est valide que le mail parte ou non.

**c.** Non, la création ne doit pas être annulée — et c'est précisément ce qui
prouve le placement. Si la réponse avait été « oui, un user sans mail de
bienvenue est un état invalide », l'envoi ferait partie de la cohérence de
l'agrégat, et il faudrait le traiter tout autrement (transaction, compensation).
Ce test remplace avantageusement l'intuition : **si l'échec de l'effet n'invalide
pas l'agrégat, c'est un effet applicatif.**

**d.** Passer par le broker plutôt que par un appel SMTP synchrone : le use case
publie un événement (`user.created`), un worker envoie le mail — exactement le
schéma de `ShareTask` / `NotifyTaskShared`
([ch. 11](11-cache-et-evenements.md)). L'API répond sans attendre le
serveur de mail, et une panne SMTP ne fait plus échouer une création. Le
compromis à connaître : le message part avant le commit, donc un mail peut être
envoyé pour un user qui n'existera jamais — c'est ce que résout un *outbox*.

**2.** `ping` est un cas limite parce qu'il ne sert à **aucun** use case métier :
c'est un besoin d'exploitation (health check). Il fait donc entrer une
préoccupation d'observabilité dans un port applicatif. Ce qui le justifie : la
seule alternative serait que l'endpoint de santé accède directement à
l'adaptateur Redis, ce qui ferait dépendre la présentation d'un détail
d'infrastructure — un couplage pire pour un bénéfice moindre. Choisir le moindre
mal en le sachant est une décision d'architecture ; le faire sans s'en rendre
compte n'en est pas une.

**3.** Le contrat `layers` : `application` importerait `presentation`, soit deux
couches au-dessus. Et concrètement, le CLI et le worker devraient construire des
objets Pydantic de l'API HTTP pour appeler un use case — ce qui rendrait le
métier dépendant d'un canal qu'ils n'utilisent pas. La « duplication » entre
`CreateTaskRequest` et `CreateTaskCommand` est apparente : les deux objets ont des
raisons de changer différentes (le contrat public de l'API vs. l'entrée du cas
d'usage).

### Chapitre 07

**1.** `TaskTitle("")` lève `EmptyTitle`, donc la lecture échoue avec une erreur
métier. Ce n'est **pas** un bug du mapper : c'est le système qui signale que la
base contient un état que le domaine considère comme impossible. C'est même une
propriété désirable — la barrière de validation joue aussi en relecture. Le vrai
bug est en amont : une donnée insérée en contournant le domaine. La parade
structurelle est une contrainte `CHECK` en base, qui interdit l'insertion fautive.

**2.** Seulement `presentation/` : le schéma de réponse et le router (ou un
`Response` personnalisé). **Zéro ligne** dans `domain/` et `application/` — le use
case renvoie déjà un DTO neutre. C'est la démonstration la plus courte de ce que
cette architecture achète.

**3.** Dans le worker, `process_message` traite un message puis, en cas d'échec
SMTP partiel, publie vers la DLQ avant que la session ne commit. Si `save()`
committait de son côté, une exception survenant **après** ce commit mais avant la
fin du traitement laisserait la base modifiée alors que le message est rejeté et
rejoué : le rollback du wrapper n'aurait plus rien à annuler. On obtiendrait des
effets partiels rejoués — le pire des deux mondes.

### Chapitre 08

**1.** `ShareTask` vérifie l'existence de la tâche, publie sur RabbitMQ, puis rend
la main. La dépendance de session commit **ensuite**. Si le commit échoue (conflit,
connexion perdue, panne PgBouncer), la transaction est annulée — mais le message
est déjà dans le broker. Le worker le consomme, charge la tâche… qui n'existe pas,
ou existe dans un état antérieur. Le pattern outbox supprime cette fenêtre en
rendant la publication elle-même transactionnelle.

**2.** Non, 503 est trompeur : une adresse mal formée est une erreur du client,
pas une panne de dépendance. Le bon traitement est en amont — `Email` est un value
object qui rejette la forme invalide à la construction, donc l'adresse n'aurait
jamais dû atteindre l'adaptateur SMTP. C'est une illustration du principe
*always-valid* : quand une erreur technique révèle une donnée invalide, la
correction se fait à la barrière de validation, pas dans le handler d'erreur.

**3.** **Zéro.** Les deux exceptions héritent de bases déjà enregistrées, et
FastAPI remonte la hiérarchie de classes pour trouver le handler. C'est tout
l'intérêt de mapper les **bases sémantiques** plutôt que les exceptions concrètes :
le coût d'ajout d'un contexte reste constant.

### Chapitre 09

**1.a.** Quelque chose comme :

```python
@dataclass(frozen=True, slots=True)
class MyTaskListItem:
    task_id: str
    title: str
    status: str
    owner_name: str

class TaskQueryPort(ABC):
    async def recent_with_owner(self, owner_id: str, *, limit: int = 20) -> list[MyTaskListItem]: ...
    async def count_by_owner(self, owner_id: str) -> int: ...
```

Le dépôt contient la version non filtrée de ce port —
`application/task/queries.py` — qui sert l'export global : même DTO plat, même
absence de use case, mais un `AsyncIterator` plutôt qu'une `list`, parce que
l'export n'est pas borné par un `limit`.

**b.** **Deux** requêtes : un `SELECT … JOIN … LIMIT 20` et un `COUNT(*)`. On
pourrait descendre à une seule avec une fonction de fenêtrage
(`COUNT(*) OVER ()`), mais deux requêtes simples valent souvent mieux qu'une
requête astucieuse — surtout si le compteur est mis en cache plus tard.

**c.** Pas dans `TaskRepository` parce qu'un repository est le port de persistance
d'un **agrégat** : il parle en `Task`, en entités complètes, et sert les
écritures. Y ajouter des projections jointes le transformerait progressivement en
couche d'accès aux données générique — et ferait entrer `UserModel` dans les
préoccupations du contexte `task`.

**2.** Deux raisons. **(a) Ça ne réutilise rien d'utile** : le mapper construit
des value objects (`TaskTitle`, `TaskId`) à partir de colonnes déjà validées, et
la vue a besoin de `str`. On paierait la reconstruction complète du modèle métier
pour la défaire aussitôt. **(b) Ça rouvre la porte qu'on vient de fermer** : une
entité renvoyée par une lecture finit toujours par être passée à un use case
d'écriture « puisqu'on l'a déjà sous la main » — et là, elle est incomplète ou
périmée. Un DTO plat ne peut pas être confondu avec un agrégat.

**3.** On perdrait la distinction entre *404 « user inconnu »* et *200 avec liste
vide* : une seule requête filtrée sur `owner_id` renvoie `[]` dans les deux cas,
et l'appelant ne peut plus savoir s'il s'est trompé d'identifiant. Un query
service rend les deux en une requête, par exemple avec un `LEFT JOIN` depuis
`users` : zéro ligne ⇒ le user n'existe pas ; une ligne avec des colonnes de tâche
nulles ⇒ le user existe et n'a pas de tâche.

### Chapitre 10

**1.a.** Deux raisons, et elles ne sont pas de même nature. **(i)** La durée : un
import tient des minutes, là où une requête HTTP doit rendre la main. Chaque
intermédiaire — proxy, ingress, client — a son délai d'expiration, et un
navigateur qui réessaie relancerait l'import depuis le début. **(ii)** La
frontière transactionnelle : `get_session` committe *à la fin de la requête*,
alors que l'import committe lot par lot. Les deux découpages se contrediraient,
et surtout un échec en cours de route laisserait un état **partiellement importé**
qu'aucun code de statut HTTP ne sait décrire — 200 serait faux, 500 aussi.

**1.b.** Si le besoin est réel, on sépare le déclenchement du traitement : la
route accepte le fichier, le range, publie un message et rend un `202 Accepted`
avec un identifiant de tâche. Le worker exécute l'import ; une seconde route rend
le rapport. La requête HTTP redevient courte, et le traitement long retrouve
l'adaptateur driving qui lui convient.

**2.** Trois choses. **(a)** Les invariants inter-champs : plus rien ne vérifie
qu'un `status` et un `completed_at` sont cohérents, et un value object ne peut
pas le faire à sa place. **(b)** L'intention : `Task(...)` ne dit pas si l'on crée
ou si l'on relit, alors que le nom `reconstitute` signale que l'identité et les
dates viennent du dehors. **(c)** La distinction de confiance entre le mapper et
l'import : `to_domain` relit notre base et lui fait confiance ; les fusionner
oblige soit à faire payer la validation à chaque lecture (et à risquer de faire
échouer la relecture de données anciennes), soit à ne plus valider les imports.

**3.** Pas dans le générateur — il est correct. Il faut regarder ce qui
**s'accumule d'un lot à l'autre**, c'est-à-dire le rapport lui-même : la liste des
rejets est non bornée, et surtout l'ensemble des identités déjà vues (utilisé pour
détecter les doublons du fichier) grandit avec le nombre de lignes — 5 millions
d'UUID représentent plusieurs centaines de Mio. C'est une limite réelle de cette
implémentation, assumée à l'échelle d'un export applicatif. Deux sorties : borner
les rejets conservés (les *n* premiers, puis un simple compteur), et abandonner la
déduplication globale en la déléguant à `ON CONFLICT` — on perd la distinction
entre « doublon du fichier » et « déjà en base », on gagne une mémoire constante.

**4.** `DO UPDATE` écrirait directement dans la ligne d'un agrégat **sans passer
par ses transitions** : on pourrait ramener une tâche `done` à `todo`, ce que
`Task.complete()` interdit précisément (`TaskAlreadyCompleted`, chapitre 04). Un
`INSERT` groupé est acceptable parce qu'une insertion ne traverse aucune
transition ; une mise à jour, si. Il faut donc soit garder l'import en insertion
seule et faire passer les modifications par le chemin d'écriture normal (charger
l'agrégat, appliquer la transition, sauvegarder), soit — si la mise à jour en
masse est un vrai besoin — la modéliser comme une opération métier explicite, avec
ses propres règles sur ce qui a le droit de changer.

### Chapitre 11

**1.** `RenameUser` invalide `user:{id}` mais pas `users:all`, qui contiendrait
toujours l'ancien nom. Deux stratégies : (a) invalidation explicite de toutes les
clés dérivées à chaque mutation — simple, mais la liste des clés à connaître
grandit et finit par être oubliée ; (b) ne pas cacher les listes, ou leur donner
un TTL court et assumer une fenêtre d'obsolescence. En pratique, (b) est souvent
le bon compromis : les listes sont peu coûteuses à recalculer et leur
invalidation est le principal générateur de bugs de cache.

**2.** Parce que le cache traiterait le symptôme sans toucher à la cause : les 51
requêtes sont toujours émises au premier appel, à chaque expiration, et pour
chaque variante de paramètres. Un déploiement, un redémarrage ou une purge suffit
à faire réapparaître le pic — au pire moment, c'est-à-dire quand le trafic
reprend. Avant de cacher : **corriger la requête** (une jointure, un query
service). Ensuite seulement, se demander si le cache apporte encore quelque
chose — souvent, la réponse est non.

**3.** Le use case renvoie un `NotifyResult` contenant les destinataires en échec ;
le worker publie alors un message vers la DLQ (`reason="smtp_send_failed"`). Le
message principal est acquitté parce qu'il **a été traité** : le rejouer
renverrait les e-mails aux destinataires qui les ont déjà reçus. On sépare donc
« le message a été consommé » de « tous ses effets ont réussi » — et la DLQ porte
la seconde information. Sans ce `publish` explicite, ces échecs partiels seraient
silencieusement perdus, puisqu'un message acquitté n'est jamais dead-letté.

**4.** Non. Un seul consommateur (rien à découpler), un seul e-mail (rien à
lisser), pas de pic (rien à tamponner) : les trois raisons d'avoir un broker
tombent. Un `BackgroundTasks` FastAPI suffit, et t'épargne un composant avec état
plus un processus worker. Ce que tu perds : la durabilité — si le processus
redémarre entre la réponse HTTP et l'envoi, l'e-mail de bienvenue disparaît sans
trace, alors qu'un message publié dans une file durable aurait survécu. Le bon
réflexe est de le noter comme un compromis assumé, et de rebasculer sur le broker
au premier des trois signaux qui apparaît — typiquement le deuxième consommateur
(analytics, CRM) qui vient se greffer sur « un utilisateur vient d'être créé ».

### Chapitre 12

**1.** Au niveau **domaine** : c'est une règle de validité du titre, donc dans
`TaskTitle`. Deux ou trois tests unitaires suffisent (titre avec URL rejeté, titre
sans URL accepté, et un cas limite genre `"exemple.com"` selon la définition
retenue). **Aucun** test d'intégration : il ne prouverait rien de plus et
coûterait des secondes. Si l'API doit renvoyer un message d'erreur particulier,
alors *ça* est testable en intégration — mais c'est un autre test.

**2.** On perdrait la vérification que les erreurs déclenchent bien un
**rollback**. Concrètement : un test qui poste une tâche avec un owner inexistant
et vérifie ensuite qu'aucune ligne parasite ne subsiste ne prouverait plus rien.
Reproduire la frontière transactionnelle réelle dans les tests n'est pas de la
symétrie décorative — c'est ce qui rend le test représentatif de la production.

**3.** Un `INSERT` peut créer un état que le domaine n'aurait jamais produit :
titre vide, `completed_at` renseigné sur une tâche `TODO`, e-mail non normalisé.
Le test passerait alors sur une situation impossible, et pire, un test de lecture
pourrait « valider » un comportement pour des données qui ne peuvent pas exister.
Semer par les use cases garantit que l'état de départ est atteignable par le
chemin d'écriture réel.

### Chapitre 13

**1.** Niveaux 1 et 2, probablement pas plus. Un value object pour la signature du
webhook et l'identifiant d'événement (validation à la construction) et une petite
entité qui protège l'idempotence (« un événement déjà traité ne se retraite pas »)
apportent beaucoup pour presque rien. Les ports et mappers n'apporteraient rien :
la complexité de ce service est technique (signatures, retries, ordre des
événements), pas métier — c'est exactement le profil décrit dans « quand ne pas
utiliser cette architecture ».

**2.** Par exemple : `catalog`, `ordering`, `shipping`. Le mot **`Product`** n'a
pas le même sens dans `catalog` (description, photos, prix affiché, catégories)
et dans `ordering` (référence, prix figé au moment de la commande, quantité). Le
mot **`Customer`** diffère aussi entre `ordering` (adresse de facturation, moyens
de paiement) et `shipping` (adresse de livraison, créneaux, contraintes d'accès).
Ce n'est pas de la duplication à éliminer : ce sont deux concepts qui portent le
même nom.

**3.** Pas de corrigé — c'est l'exercice le plus utile du cours. Le correctif le
moins coûteux est presque toujours le même : sortir les règles des routers vers
les entités et les value objects (niveaux 1 et 2 de l'« entre-deux »), avant
d'introduire le moindre port.
