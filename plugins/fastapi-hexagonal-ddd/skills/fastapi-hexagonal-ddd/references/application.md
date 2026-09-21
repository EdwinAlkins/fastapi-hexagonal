# The application layer: use cases, ports, DTOs

The application layer **orchestrates**. It does not hold domain invariants; it
may hold the policy of a use case.

## Ports: who declares the need?

A port is an interface expressing a need without saying how it is met. The
interesting question is **which layer declares it**, and the answer is always
the same question back: **who needs this concept?**

- "I must be able to find a `Task` by its identity" is expressed in domain
  vocabulary, but placement still depends on **who needs that capability**.
  Classical DDD puts aggregate repositories in `domain/`; an architecture where
  only use cases request persistence may put them in `application/`. This
  template deliberately chooses `domain/<context>/repository.py`.
- "I cache some reads" belongs to nobody in the business. No invariant of `Task`
  or `User` depends on it. It is a **use-case decision** — the port lives in
  `application/shared/cache.py`.

| Port | Location | Why there |
|---|---|---|
| `TaskRepository`, `UserRepository` | `domain/<ctx>/repository.py` **in this template** | Classical DDD choice for aggregate lifecycle; `application/` is also coherent when use cases own the need |
| `CachePort` | `application/shared/cache.py` | Read optimisation decided by use cases |
| `SMTPSenderPort` | `application/shared/smtp.py` | Notification: applicative effect, not an invariant |
| `EventPublisherPort` | `application/shared/messaging.py` | Integration concern |
| `EmailTemplatePort` | `application/shared/html_template/` | Message rendering: a presentation detail |
| `TaskBulkWriterPort` | `application/<ctx>/bulk.py` | Grouped transport, distinct from the aggregate port |
| `UnitOfWorkPort` | `application/shared/unit_of_work.py` | Explicit commit points for long use cases |

A useful placement test, borrowed from a concrete case: *"if sending the welcome
email fails, must the user creation be rolled back?"* If the answer is no, the
effect is applicative and its port belongs in `application/`. If the answer had
been yes, the effect would be part of the aggregate's coherence and would need
entirely different treatment.

```python
# domain/task/repository.py
class TaskRepository(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None: ...
    @abstractmethod
    async def get(self, task_id: TaskId) -> Task: ...
    @abstractmethod
    async def delete(self, task_id: TaskId) -> None: ...
    @abstractmethod
    async def exists(self, task_id: TaskId) -> bool: ...
```

### What a port must not expose

A port leaks the moment its implementation shows through.

- **No lifecycle management.** `EventPublisherPort` exposes `publish` — not
  `connect`, not `close`. The AMQP connection lifecycle is infrastructure,
  opened in the API lifespan or at worker startup.
- **No transport vocabulary.** `publish(routing_key: str, payload: dict)` is
  already a leak: it forces the use case to serialise and to know about *routing
  keys*, which is AMQP vocabulary. Pass a typed event that carries its own type;
  let the adapter turn it into a routing key — a Kafka adapter would make it a
  topic.
- **No `execute(sql: str)`, no `get_session()`.** That is not a port; that is the
  ORM wearing a costume.

### Typed or opaque? Not a single rule

`CachePort` legitimately speaks in JSON-compatible dicts while
`EventPublisherPort` speaks in typed events. That is not an inconsistency:

|  | `EventPublisherPort` | `CachePort` |
|---|---|---|
| Who reads the data | **another process** | the same use case, later |
| Lifetime | public, versioned contract | ephemeral, disposable |
| Cost of a shape change | coordinate two deployments | nothing, at worst a cache miss |
| Typing worth it? | **yes** | no, it would be ceremony |

> A contract read by someone else gets typed; a private, disposable detail may
> stay opaque.

### Pagination belongs to the read need

`limit` / `offset` are legitimate **application policy**, but that is precisely
why a paginated endpoint query usually belongs on an application query port:

```python
class TaskQueries(ABC):
    async def list_by_owner(
        self, owner_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[TaskSummary]: ...
```

Keep `TaskRepository` focused on aggregate lifecycle (`get`, `save`, `delete`).
Add a repository search only when its caller needs the returned aggregates to
protect invariants. A read-only list should return read models instead. SQL
syntax such as `ORDER BY ... NULLS LAST` never belongs in either port; if order
is genuinely business-significant, name the policy in business language.

## Use cases

One use case per business action. It receives its ports at construction and
exposes `execute`. It loads, calls the domain, saves.

```python
class CompleteTask:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(self, task_id: str) -> TaskDTO:
        task = await self._repository.get(TaskId.from_string(task_id))
        task.complete()                       # ← the decision lives in the DOMAIN
        await self._repository.save(task)
        return TaskDTO.from_entity(task)
```

The decision ("may this be completed?") is not here. The use case coordinates.

### Cross-aggregate orchestration

When an action touches several aggregates, the use case depends on several
ports:

```python
class CreateTask:
    def __init__(self, tasks: TaskRepository, users: UserRepository) -> None:
        self._tasks, self._users = tasks, users

    async def execute(self, command: CreateTaskCommand) -> TaskDTO:
        owner_id = UserId.from_string(command.owner_id)
        if not await self._users.exists(owner_id):
            raise UserNotFound(str(owner_id))          # referential coherence
        task = Task.create(owner_id=owner_id, title=TaskTitle(command.title))
        await self._tasks.save(task)
        return TaskDTO.from_entity(task)
```

The application coordinates rules spanning several aggregates; the domain keeps
each aggregate coherent in isolation.

### Mixing business and technical ports

```python
class GetUser:
    def __init__(self, repository: UserRepository, cache: CachePort) -> None: ...

    async def execute(self, user_id: str) -> UserDTO:
        identity = UserId.from_string(user_id)   # validate BEFORE touching the cache
        key = f"user:{identity}"

        cached = await self._cache.get(key)
        if cached is not None:
            return self._from_cache(cached)

        user = await self._repository.get(identity)
        dto = UserDTO.from_entity(user)
        await self._cache.set(key, asdict(dto))
        return dto
```

Three details separating "it works" from "it is correct":

- **Identity is validated before the cache.** A syntactically invalid ID
  triggers no read and creates no entry.
- **The invalidation contract is written in the docstring**: the key is
  `user:{id}`, and every mutation of a `User` must delete it. A cache whose
  invalidation nobody documents is a bug waiting for its moment.
- **Rebuilding from the cache is explicit.** JSON has no `datetime`.

## DTOs

A use case does not return a domain entity to the API, and does not accept a
Pydantic schema. The first couples the public contract to the business model,
the second brings the web framework into the application layer.

```python
@dataclass(frozen=True, slots=True)
class CreateTaskCommand:        # input: a "command"
    owner_id: str
    title: str
    description: str | None = None

@dataclass(frozen=True, slots=True)
class TaskDTO:                  # output
    id: str
    owner_id: str
    title: str
    # …
    @classmethod
    def from_entity(cls, task: Task) -> TaskDTO: ...
```

Three concrete reasons not to expose the entity:

1. **Contract coupling.** Renaming a domain attribute would break the public API.
2. **Internal state leakage.** An entity exposes mutation methods
   (`complete`, `rename`) that are meaningless in an HTTP response.
3. **Serialisation.** A DTO speaks in simple types, which makes it trivial to
   serialise — and to cache.

A DTO containing `owner: User` misses the point: it reintroduces the
inter-aggregate navigation you removed.

## The opposite trap: ceremony

Everything above justifies successive translations. You must also know when they
become absurd. Count the representations of one concept:

```
CreateUserRequest    (HTTP schema, presentation)
CreateUserCommand    (input DTO, application)
User                 (entity, domain)
UserDTO              (output DTO, application)
UserResponse         (HTTP schema, presentation)
UserModel            (ORM model, infrastructure)
```

**Six classes to carry a name and an email.** For a long-lived system with a rich
domain, perfectly reasonable — each has a different reason to change, which is
exactly what lets the API evolve without touching the domain. For a 400-line
administrative CRUD that will never grow, it is absurd, and saying so is part of
the job.

Three questions to decide, **object by object**, not in bulk:

1. **Do these two representations have different reasons to change?** If the HTTP
   schema and the input DTO will always change together and for the same reason,
   one of them is noise.
2. **Is there a second caller, real or likely?** A CLI and a worker alone justify
   `CreateUserCommand`: without it, they would depend on a Pydantic object
   designed for HTTP.
3. **Does the domain have a different shape from the transport?** The entity
   carries value objects; the response carries strings. When the two shapes are
   identical field for field, forever, the mapper protects nothing.

The tension between isolation and ceremony is not settled once — it is rejudged
at every layer you add.

## The full request flow

```
Client → Router (validates the transport schema)
       → Use case (execute(Command))
           → port: users.exists(owner_id)        → SELECT
           → domain: Task.create(...)            → always-valid entity
           → port: tasks.save(task)              → INSERT, no commit here
       ← TaskDTO
       ← 201 + TaskResponse
                         commit happens at the transaction boundary
```

The use case is testable with no FastAPI and no database: hand it a command and
in-memory ports, assert on the returned DTO. That level of test exists **only**
because the use case depends on ports alone.
