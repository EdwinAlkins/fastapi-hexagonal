# 3. Application & use cases

La couche application est fine. Elle ne contient **aucune règle métier** (elles
sont dans le domaine) ni **aucune technique** (elle est dans les adaptateurs).
Son rôle : **orchestrer**. Un use case par action applicative.

## Les ports : le domaine déclare ses besoins

Un **port** est une interface définie *par le domaine*, exprimant ce dont il a
besoin — sans dire comment ce sera réalisé. Le port de persistance des tâches
(`domain/task/repository.py`) :

```python
class TaskRepository(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None: ...
    @abstractmethod
    async def get(self, task_id: TaskId) -> Task: ...
    @abstractmethod
    async def list_by_owner(self, owner_id: UserId, *, limit=100, offset=0) -> list[Task]: ...
    @abstractmethod
    async def delete(self, task_id: TaskId) -> None: ...
```

Remarque : le port vit **dans le domaine**, pas dans l'infrastructure. C'est
l'**inversion de dépendance** : le domaine possède l'interface, l'infrastructure
lui obéit. L'implémentation concrète (`SqlAlchemyTaskRepository`) viendra se
brancher dessus (chapitre 4).

## Le use case : orchestrer, pas décider

Un use case reçoit ses dépendances (les ports) à la construction, et expose une
méthode `execute`. Il enchaîne : charger → appeler le domaine → sauvegarder.

```python
class CompleteTask:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str) -> TaskDTO:
        task = await self._repository.get(TaskId.from_string(task_id))
        task.complete()                       # ← la règle est DANS le domaine
        await self._repository.save(task)
        return TaskDTO.from_entity(task)
```

Noter que la décision (« peut-on compléter ? ») n'est pas dans le use case :
elle est dans `task.complete()`. Le use case ne fait que coordonner.

## Orchestration inter-agrégats

Quand une action touche plusieurs agrégats, le use case dépend de **plusieurs
ports**. Exemple : créer une tâche exige que son propriétaire existe. `CreateTask`
dépend donc des deux repositories :

```python
class CreateTask:
    def __init__(self, tasks: TaskRepository, users: UserRepository) -> None:
        self._tasks = tasks
        self._users = users

    async def execute(self, command: CreateTaskCommand) -> TaskDTO:
        owner_id = UserId.from_string(command.owner_id)
        if not await self._users.exists(owner_id):
            raise UserNotFound(str(owner_id))         # cohérence référentielle
        task = Task.create(owner_id=owner_id, title=TaskTitle(command.title))
        await self._tasks.save(task)
        return TaskDTO.from_entity(task)
```

C'est la **couche application** qui coordonne des règles impliquant plusieurs
agrégats — le domaine, lui, garde chaque agrégat cohérent isolément.

## Les DTO : découpler l'application des frontières

Un use case ne doit pas renvoyer une entité du domaine directement à l'API (ça
coupleraient les deux), ni recevoir un schéma Pydantic (ça ferait entrer le
framework dans l'application). On utilise des **DTO** : des structures neutres.

```python
@dataclass(frozen=True, slots=True)
class CreateTaskCommand:        # entrée : « commande »
    owner_id: str
    title: str
    description: str | None = None

@dataclass(frozen=True, slots=True)
class TaskDTO:                  # sortie
    id: str
    owner_id: str
    title: str
    # ...
    @classmethod
    def from_entity(cls, task: Task) -> TaskDTO: ...
```

Ainsi le use case est testable sans FastAPI ni Pydantic : on lui passe une
`CreateTaskCommand`, on vérifie le `TaskDTO` renvoyé. Rapide, pur.

## Le flux complet d'une requête

```
HTTP → Router → (traduit en Command) → Use case → Port → Adaptateur → BDD
                                          │
                                    appelle le Domaine (règles)
                                          │
HTTP ← Router ← (TaskDTO → schéma) ← Use case
```

## À retenir

- Le **port** est une interface **du domaine** ; l'infra l'implémente (inversion de dépendance).
- Un **use case** orchestre (charger → domaine → sauver), il ne contient pas la règle.
- Une action multi-agrégats → un use case qui dépend de **plusieurs ports**.
- Les **DTO** isolent l'application des frameworks des deux côtés.
