# 2. Le domaine (DDD tactique)

Le domaine est le cœur. C'est là que vivent les **règles métier**, exprimées
avec les mots du métier, sans aucune technique. Le DDD *tactique* fournit
quelques briques pour le construire : les **value objects**, les **entités**,
les **agrégats**.

## Value objects : définis par leur valeur

Un value object n'a pas d'identité : deux value objects avec la même valeur sont
interchangeables. Ils sont **immuables** et **s'auto-valident à la
construction** — ce qui garantit le principe *always-valid model* : un objet qui
existe est forcément dans un état valide.

Exemple (`domain/task/value_objects.py`) :

```python
@dataclass(frozen=True, slots=True)   # frozen = immuable
class TaskTitle:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        if not cleaned:
            raise EmptyTitle()                 # invalide → on ne construit pas
        if len(cleaned) > TITLE_MAX_LENGTH:
            raise TitleTooLong(TITLE_MAX_LENGTH)
        object.__setattr__(self, "value", cleaned)   # normalisation
```

Le gain : partout ailleurs dans le code, dès que tu as un `TaskTitle`, tu **sais**
qu'il est valide. Plus besoin de re-vérifier « et si le titre était vide ? ».
La validation est faite **une fois, au bon endroit**.

Autres exemples dans le projet : `Email` (format vérifié, normalisé en
minuscules), `UserId` (encapsule un UUID), `TaskStatus` (énumération d'états).

## Entités : définies par leur identité

Une entité a une **identité stable dans le temps**. Une `Task` reste « la même
tâche » même si son titre ou son statut change. Deux entités sont égales si elles
ont le même identifiant — pas la même valeur.

```python
class Task:
    def __eq__(self, other: object) -> bool:
        # Égalité par identité, pas par valeur.
        return isinstance(other, Task) and other.id == self.id
```

## Les invariants vivent dans l'entité

Un **invariant** est une règle qui doit toujours rester vraie. Le point crucial :
l'entité **protège ses propres invariants** via ses méthodes. On ne modifie pas
son état de l'extérieur en tripotant ses attributs.

```python
class Task:
    def complete(self) -> None:
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyCompleted()   # invariant : pas deux fois
        self.status = TaskStatus.DONE
        self.completed_at = _now()
```

Comparons deux styles :

```python
task.status = "done"          # ❌ contourne la règle, état incohérent possible
task.complete()               # ✅ la règle est garantie par l'entité
```

C'est ce qu'on appelle un **modèle riche** (l'objet a du comportement), par
opposition à un **modèle anémique** (un simple sac de données que du code
extérieur manipule). Le DDD vise le modèle riche.

## Agrégat : l'unité de cohérence

Un agrégat est un groupe d'objets qu'on traite comme un tout, avec une **racine**
(ici, `Task`). Toute modification passe par la racine, qui garantit la cohérence
de l'ensemble. Règle d'or : **un agrégat ne référence pas un autre agrégat
directement, mais par son identité** (voir chapitre 5).

## Les exceptions métier

Les erreurs du domaine sont des **exceptions métier**, pas des codes HTTP. Le
domaine ignore HTTP. Il lève `TaskNotFound`, `EmailAlreadyUsed`… et c'est la
présentation qui les traduira en 404, 409, etc. (chapitre 6).

Toutes héritent d'une base commune (`domain/shared/exceptions.py`) :

```python
class DomainError(Exception): ...
class ValidationError(DomainError): ...   # invariant de VO non respecté
class NotFoundError(DomainError): ...     # ressource introuvable
class ConflictError(DomainError): ...     # conflit d'unicité / d'état
```

## Pourquoi pas Pydantic dans le domaine ?

Question fréquente : ce serait plus court. Mais Pydantic est un outil de
**validation de données aux frontières** (parser du JSON, des variables d'env),
avec son propre cycle de vie (la migration v1→v2 fut une réécriture). Si le cœur
en dépend, une montée de version du framework devient une migration de ton
métier — l'endroit qui devrait être le plus stable. Les `dataclass` de la
bibliothèque standard offrent 90 % du confort, **zéro dépendance**. On garde
Pydantic là où c'est son rôle : les schémas HTTP et la config.

## À retenir

- **Value object** : valeur, immuable, auto-validé → *always-valid*.
- **Entité** : identité stable, égalité par id.
- **Invariants dans l'entité** : on change l'état via des méthodes, pas des attributs.
- Modèle **riche** (comportement) > modèle **anémique** (données nues).
- Le domaine lève des **exceptions métier**, ignore HTTP, et n'importe aucun framework.
