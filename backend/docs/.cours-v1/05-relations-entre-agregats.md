# 5. Relations entre agrégats

C'est le point le plus subtil du DDD, et celui qui fait la différence entre un
modèle propre et un modèle qui se transforme en plat de spaghettis. On part de
l'exemple concret du projet — **un `User` possède plusieurs `Task`** (1→n) —
puis on généralise aux autres cardinalités (n→1, 1↔1, n↔n).

## La règle d'or : référencer par identité, pas par navigation

Réflexe habituel (issu de l'ORM) : mettre un objet `User` dans `Task`, et une
liste `List[Task]` dans `User`. **En DDD, on ne fait pas ça.** Un agrégat en
référence un autre **par son identité** (l'ID), jamais par l'objet lui-même.

```python
# domain/task/entities.py
class Task:
    def __init__(self, *, id: TaskId, owner_id: UserId, ...):
        self.owner_id = owner_id     # ✅ une IDENTITÉ, pas un objet User
```

Et symétriquement, `User` **ne porte pas** la collection de ses tâches.

Pourquoi cette rigueur ?

- **Frontières de cohérence.** Chaque agrégat est une unité transactionnelle.
  Si `User` contenait ses `Task`, charger un user chargerait toutes ses tâches,
  et les règles des deux se mélangeraient.
- **Découplage.** Le domaine `task` n'a pas besoin de connaître le nom ou
  l'email du user pour appliquer ses règles — juste *à qui* la tâche appartient.
- **Scalabilité.** Un user peut avoir 10 000 tâches. Une collection en mémoire
  n'a aucun sens.

## « Les tâches d'un user » est une *requête*, pas une navigation

Puisque `User` ne porte pas ses tâches, comment les obtenir ? Par une **requête**
sur le port du contexte `task` :

```python
# domain/task/repository.py
async def list_by_owner(self, owner_id: UserId, *, limit=100, offset=0) -> list[Task]: ...
```

La navigation « user → ses tâches » devient un appel explicite, pas un attribut.

## Où vit la vraie jointure ? Dans l'infrastructure uniquement

La relation relationnelle (clé étrangère, jointure SQL) est un **détail
d'infrastructure**. Elle apparaît seulement au niveau ORM :

```python
# infrastructure/persistence/task/models.py
owner_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), index=True    # la FK
)
```

Le domaine ignore tout de cette clé étrangère : il ne connaît qu'un `UserId`.

## Qui vérifie que le user existe ? La couche application

La clé étrangère garantit l'intégrité *en base*, mais on veut aussi une erreur
métier claire. C'est le use case qui orchestre cette vérification inter-agrégats
(vu au chapitre 3) :

```python
if not await self._users.exists(owner_id):
    raise UserNotFound(str(owner_id))
```

## Le piège classique : le N+1 (côté lecture)

Si un jour tu veux charger un `User` **avec** ses tâches (pour une vue de
lecture), attention : en SQLAlchemy **async**, le chargement paresseux implicite
est interdit — ce qui t'oblige à être explicite, et c'est une bonne chose :

```python
select(UserModel).options(selectinload(UserModel.tasks))   # 1 requête, pas N
```

Sans ça, tu ferais une requête par user → le fameux problème **N+1**.

## Et si je veux une vue jointe (tâche + nom du propriétaire) ?

Ne la fais **pas** passer par les agrégats. C'est une **lecture** : crée un
*query service* dans l'infra qui fait un `SELECT ... JOIN` et retourne
directement un DTO de lecture. Les agrégats servent aux **écritures** (garantir
les invariants) ; les vues jointes servent aux **lectures**. Cette séparation
lecture/écriture est l'idée de base de **CQRS**.

## Les autres cardinalités

Le **principe directeur ne change jamais** : référence par identité, la jointure
est un détail d'infra. Seule la *forme* de la référence change. (Les exemples
ci-dessous sont illustratifs — le code ne contient que le 1→n.)

### n→1 : c'est déjà fait

Un `n→1` est simplement un `1→n` vu de l'autre côté. Et c'est *exactement* ce
qu'on a implémenté : `Task.owner_id` est une relation n→1 (plusieurs tâches → un
user). Autrement dit :

> Un `1→n` s'implémente **toujours** par son côté `n→1` : c'est l'**enfant** qui
> porte l'identité du parent, jamais le parent qui porte une collection d'objets.

Il n'y a donc rien de nouveau à faire : le côté « plusieurs » porte un champ
`parent_id`, et « les enfants du parent » restent une requête (`list_by_owner`).

### 1↔1 : d'abord, est-ce vraiment deux agrégats ?

Face à un `1↔1`, la première question n'est pas « comment le mapper » mais
« devrait-ce être **un seul** agrégat ? ». Un 1↔1 signale souvent que :

- **Ce n'est qu'un value object.** `User` et son unique `Address` → l'adresse est
  un value object *à l'intérieur* de `User`, pas un agrégat séparé. Pas de relation
  du tout : c'est de la composition.
- **Ce sont deux vrais agrégats** avec des cycles de vie indépendants (ex.
  `User` ↔ `BillingAccount` gérés séparément). Dans ce cas : **un seul côté porte
  l'identité de l'autre** (le côté dépendant, ou le « propriétaire » de la
  relation). On **évite les références mutuelles** (A→B *et* B→A) qui créent un
  couplage circulaire. En base : une FK avec contrainte `UNIQUE`.

Règle pratique : par défaut, penche pour **fusionner** (value object). Ne sépare
en deux agrégats que si tu as une vraie raison (cohérence ou cycle de vie distincts).

### n↔n : deux stratégies

Un `n↔n` (ex. `Article` ↔ `Tag`, `Student` ↔ `Course`) se modélise de deux façons.

1. **Collections d'identités**, si les ensembles sont petits et la relation ne
   porte **aucune donnée** propre :

   ```python
   class Article:
       def __init__(self, ..., tag_ids: set[TagId]) -> None:
           self._tag_ids = tag_ids        # des IDENTITÉS, pas des objets Tag
   ```

2. **Réifier la relation en agrégat** — souvent le meilleur choix, surtout quand
   la relation **porte ses propres attributs**. `Student ↔ Course` avec une date
   d'inscription et une note *n'est pas* une simple association : c'est un concept
   métier, `Enrollment` :

   ```python
   class Enrollment:                       # la relation DEVIENT un agrégat
       student_id: StudentId
       course_id: CourseId
       enrolled_at: datetime
       grade: Grade | None
   ```

   Dès qu'on se surprend à vouloir « stocker quelque chose sur la relation »,
   c'est le signal de la réifier.

> **Le piège n↔n :** ne jamais modéliser ça comme deux collections d'objets qui
> se pointent mutuellement (`user.roles` ↔ `role.users`). C'est l'anti-pattern
> qui fait exploser le chargement (N+1, cycles) et dissout les frontières
> d'agrégats. En infra, le n↔n se traduit par une **table de jointure** — mais ça
> reste, comme toujours, un détail d'infrastructure.

### En résumé des cardinalités

| Relation | Modélisation domaine | Infra |
|----------|----------------------|-------|
| 1→n / n→1 | l'enfant porte `parent_id: ParentId` | FK indexée |
| 1↔1 (2 agrégats) | un seul côté porte l'ID de l'autre | FK `UNIQUE` |
| 1↔1 (en fait 1) | value object composé dans l'agrégat | colonnes inline |
| n↔n (sans données) | collection d'`Id` d'un côté | table de jointure |
| n↔n (avec données) | agrégat de relation réifié (`Enrollment`) | table-entité |

## Récapitulatif par couche

Pour le 1→n du projet, concrètement :

| Couche | Comment la relation apparaît |
|--------|------------------------------|
| Domain | Par identité : `Task.owner_id: UserId`. Pas de collection dans `User`. |
| Application | Use cases orchestrant deux ports (vérif d'existence). |
| Infrastructure | La vraie jointure SQL : `ForeignKey`, `relationship`, `selectinload`. |
| Presentation | Routes imbriquées `/users/{id}/tasks` ; le DTO expose `owner_id`. |

## À retenir

- On référence un autre agrégat **par son ID**, jamais par l'objet — **quelle que
  soit la cardinalité**.
- « Les enfants d'un parent » = une **requête** (`list_by_owner`), pas un attribut.
- **1→n = n→1** : c'est l'enfant qui porte `parent_id`, jamais le parent la collection.
- **1↔1** : demande-toi d'abord si ce n'est pas un seul agrégat (value object) ;
  sinon un seul côté porte l'ID.
- **n↔n** : collection d'IDs si trivial ; **réifie en agrégat** (`Enrollment`) dès
  que la relation porte des données.
- La jointure SQL est toujours un **détail d'infra** ; le domaine ne voit que des ID.
- Vue jointe en lecture → **query service** dédié (CQRS), pas les agrégats.
- En async, charge les relations **explicitement** (`selectinload`) pour éviter le N+1.
