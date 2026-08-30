# 4. Les adaptateurs

Les adaptateurs sont le monde extérieur branché sur le cœur. Deux familles : les
**driven** (pilotés — la base de données) et les **driving** (pilotants —
l'API). Ils implémentent ou consomment les ports, mais ne contiennent aucune
règle métier.

## Côté driven : la persistance

### Le modèle ORM ≠ l'entité du domaine

Tentation courante : utiliser la même classe pour l'entité métier et la ligne de
base. On l'évite **volontairement**. L'entité `Task` (domaine) et `TaskModel`
(ORM SQLAlchemy) sont deux classes distinctes. Pourquoi ? Parce que les
contraintes de la base (colonnes, types, clés étrangères) ne doivent pas
déteindre sur le modèle métier — sinon le domaine dépendrait de SQLAlchemy.

```python
# infrastructure/persistence/task/models.py
class TaskModel(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    # ...
```

### Les mappers : traduire dans les deux sens

Un **mapper** convertit entité ↔ modèle. C'est le seul endroit qui connaît les
deux formes.

```python
# infrastructure/persistence/task/mappers.py
def to_domain(model: TaskModel) -> Task:          # ORM → domaine
    return Task(id=TaskId(model.id), owner_id=UserId(model.owner_id),
                title=TaskTitle(model.title), ...)

def to_model(task: Task) -> TaskModel:            # domaine → ORM
    return TaskModel(id=task.id.value, owner_id=task.owner_id.value, ...)
```

### Le repository : implémenter le port

Le port `TaskRepository` (défini dans le domaine) est implémenté ici :

```python
# infrastructure/persistence/task/repository.py
class SqlAlchemyTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, task_id: TaskId) -> Task:
        model = await self._session.get(TaskModel, task_id.value)
        if model is None:
            raise TaskNotFound(str(task_id))
        return mappers.to_domain(model)
```

Point important : le repository **ne fait aucun `commit`**. La transaction est
gérée ailleurs (chapitre 6). Il ne fait que muter la session.

## Côté driving : l'API HTTP

### Les schémas Pydantic : le contrat du transport

Ici, Pydantic est à sa place : valider/sérialiser ce qui entre et sort en HTTP.
Ce sont des objets **de frontière**, séparés des DTO applicatifs.

```python
# presentation/api/v1/schemas/task.py
class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = None
```

### Le router : traduire HTTP ↔ use case

Le router reçoit la requête, la traduit en *command*, appelle le use case, et
reconvertit le DTO en réponse. Il ne contient pas de logique.

```python
# presentation/api/v1/routers/users.py
@router.post("/{user_id}/tasks", status_code=201)
async def create_task_for_user(
    user_id: str,
    payload: CreateTaskRequest,
    use_case: Annotated[CreateTask, Depends(get_create_task)],
) -> TaskResponse:
    dto = await use_case.execute(
        CreateTaskCommand(owner_id=user_id, title=payload.title, description=payload.description)
    )
    return TaskResponse.from_dto(dto)
```

## Deux validations, deux rôles (ne pas confondre)

Le `min_length=1` du schéma **et** le `EmptyTitle` du value object ne font pas
la même chose :

- Le **schéma** filtre le transport : renvoyer un 422 propre au client HTTP.
- Le **value object** garantit l'invariant métier, quel que soit l'appelant
  (un test, la CLI, un autre use case ne passent pas par le schéma HTTP).

La **source de vérité, c'est le domaine**. Le schéma est un filtre ergonomique
en façade. D'ailleurs `"   "` (espaces) passe `min_length=1` mais est rejeté par
le domaine.

## À retenir

- Modèle ORM et entité domaine sont **séparés**, reliés par un **mapper**.
- Le repository **implémente** le port et ne **committe pas**.
- Les **schémas** Pydantic sont le contrat HTTP, distincts des **DTO** applicatifs.
- Router et repository ne contiennent **aucune règle** : ils traduisent.
