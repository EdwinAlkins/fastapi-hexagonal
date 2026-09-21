# Architecture: the dependency rule, in depth

## Why the rule exists

Take a handler that "looks normal":

```python
@router.post("/tasks")
async def create_task(payload: CreateTaskRequest, db: AsyncSession = Depends(get_db)):
    user = await db.get(UserModel, payload.owner_id)
    if user is None:
        raise HTTPException(404, "unknown user")
    if not payload.title.strip():
        raise HTTPException(422, "empty title")
    task = TaskModel(id=uuid4(), owner_id=payload.owner_id, title=payload.title.strip(),
                     status="todo", created_at=datetime.now(UTC))
    db.add(task)
    await db.commit()
    return task
```

Nothing here is absurd. The problem is what becomes impossible:

1. **The rules have no home.** "A title cannot be empty" is a company rule
   living in an HTTP router. The day a CLI, a CSV import or a worker also
   creates tasks, it is duplicated or forgotten.
2. **Testing a rule requires the whole stack.** Three seconds of setup to test a
   string comparison. Predictable result: nobody tests it.
3. **"Complete a task" is written nowhere.** Every caller does
   `task.status = "done"` and hopes to remember `completed_at`.
4. **Changing a tool becomes a project.** All business code is entangled with it.
5. **Nobody can read the business rules.** "What are the rules of a task?" has no
   answer in any single file.

Every later pattern is machinery serving one question: **whose decision is this?**

## Driving vs. driven

- A **driving** (primary) adapter triggers the application: HTTP API, CLI,
  message consumer, scheduled job.
- A **driven** (secondary) adapter is called by the application: database,
  cache, SMTP, broker, third-party API.

The same tool can be both. A broker is driven when a use case publishes to it,
and driving when a worker consumes from it.

A use case knows neither the adapter calling it nor the adapter serving it.
That is what lets the same `CreateUser` back an HTTP route and a CLI command
without a line of adaptation — and it is the operational proof that the core is
isolated. If you cannot call your use cases from a second entry point, the
isolation is theoretical.

## Where a rule lives — worked examples

Five statements that all sound like "business rules", living in four different
places:

| Rule | Home | Why |
|---|---|---|
| A task title cannot be empty | value object | About a single isolated value, context-free |
| A finished task cannot be finished twice | entity method | A state transition of one object, from its current state |
| You cannot create a task for a non-existent user | use case | Spans two aggregates and needs I/O through a port |
| An email address is unique among users | use case **and** database **and** adapter | A property of a *set*; see the three levels below |
| `tasks.owner_id` must reference an existing user | infrastructure | A foreign key; the domain only knows a `UserId` |

### The three levels of a guarantee

Uniqueness and referential integrity are never one decision:

| Level | What it contributes |
|---|---|
| Use case queries the port first | the readable **message** in the common case |
| `UNIQUE` / `FOREIGN KEY` constraint | the real **guarantee**, including under concurrency |
| Adapter forces a `flush` and translates the violation | makes the guarantee **audible** as a business error |

The third level is the one everyone omits. A constraint violation surfaces as a
driver-level `IntegrityError` only at flush — that is, at commit, if nobody
forces it earlier. Whether that is merely ugly or actively dangerous depends on
**when your transaction commits**:

- **Commit before the response is built.** The violation propagates normally and
  your error handlers can map it. Translating it into a business error is then
  about producing a *readable* 409 instead of an opaque 500.
- **Commit after the response is built** — the classic case of a `yield`
  dependency whose teardown runs post-response. The violation fires too late to
  change the status: the client receives a full, positive `201` with a body for a
  transaction that was rolled back, while the server logs an exception. Not a
  500 — a lying success no caller can detect.

The flush is worth forcing under **both**, for different reasons: in the first
it buys the *translation* — the adapter is the only place that still knows which
constraint fired — and in the second it buys translation *and* the client ever
hearing about the failure at all.

But the third level is not a substitute for the second question. A flush is not
a commit: a deferred constraint or a failure at `COMMIT` still lands after the
flush succeeded. For state-changing HTTP methods, commit **before** building the
response, so that a 2xx means the write is durable. See
`transactions-and-errors.md`.

### Absent rules must be as explicit as present ones

If `rename()` deliberately allows renaming a completed task, say so in the
docstring. An unwritten permission looks like an oversight to the next reader,
and gets "fixed".

## Domain services and application policies

A **domain service** hosts a rule that is unmistakably business but belongs to
no entity naturally — typically because it needs several objects as equals, and
putting it in one of them would be arbitrary.

```python
class PricingService:
    """The price depends on the customer AND the order. Neither owns the rule."""
    def calculate(self, customer: Customer, order: Order) -> Money: ...
```

Guard rails:

- **Stateless**, and in this architecture **no I/O**: the application layer loads
  what it needs and passes it in. That is a convention, not DDD law — some
  designs let a domain service depend on a domain abstraction. The criterion
  that always holds: a domain service carries a **business decision**; it does
  not drive the **application workflow**.
- Named in business language (`PricingService`, `TransferPolicy`), never
  `TaskManager` or `UserHelper`.
- **Do not overuse it.** Putting everything in services produces exactly the
  anemic model you were escaping. Always ask first whether an entity could
  legitimately own the rule.

An **application policy** is a rule of the *use case*, not of the timeless
business: a daily cap, a pagination limit, a per-caller quota. Forcing it into
the domain pollutes it; denying it exists makes the architecture a lie.

## Where does a port belong?

Ask: **who expresses this need?**

| Port | Layer | Why |
|---|---|---|
| `TaskRepository`, `UserRepository` | `domain/` **in this template** | Classical DDD choice: the aggregate lifecycle is treated as part of the domain model |
| `CachePort` | `application/` | No domain invariant depends on caching; the use case decides |
| `SMTPSenderPort` | `application/` | An applicative effect, not a domain invariant |
| `EventPublisherPort` | `application/` | Integration concern |
| `UnitOfWorkPort` | `application/` | Long-running use cases request commit points explicitly |

This is where many write-ups get it wrong by asserting "ports live in the
domain". Putting `CachePort` in `domain/` would claim the business model has an
opinion about caching. It has none.

Persistence ports in the domain are the classical DDD choice, and this
template follows it. That does not make the placement universal. If only use
cases express the need to load and save aggregates, declaring the repository in
`application/` is equally coherent. Put a port in the layer that owns the need,
keep its vocabulary free of infrastructure, and state the template's choice as a
choice.

Keep read policy out of an aggregate repository. A paginated list used to serve
an endpoint belongs naturally to an application query port returning read
models. A repository query returning aggregates is justified when those
aggregates are loaded to make an invariant-protecting decision.

## Enforcing the rule

A rule that is not checked automatically degrades within months.

A `grep` is a fine reflex but not a source of truth:

```bash
grep -rE "fastapi|sqlalchemy|pydantic" src/<pkg>/domain/   # should be empty
```

It misses **transitive** imports (a "pure" domain module importing a helper that
imports SQLAlchemy) and produces false positives on comments.

The real guarantee analyses the import graph. In Python, `import-linter` in
`pyproject.toml`:

```toml
[tool.importlinter]
root_package = "task_manager"
include_external_packages = true   # required for the "forbidden" contract below

[[tool.importlinter.contracts]]
name = "Hexagonal layering"
type = "layers"
layers = [
    "task_manager.presentation",
    "task_manager.infrastructure",
    "task_manager.application",
    "task_manager.domain",
]

[[tool.importlinter.contracts]]
name = "Framework-free domain"
type = "forbidden"
source_modules = ["task_manager.domain"]
forbidden_modules = ["fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "starlette"]
```

Run it in pre-commit and CI, not just locally. Equivalents elsewhere: ArchUnit
(Java/.NET), dependency-cruiser or eslint boundaries (TypeScript), `go list` +
custom checks (Go).

> The `layers` list is a **permission ordering**, not a call chain: it says
> presentation *may* import infrastructure, not that it *should* route through
> it. A handler calls a use case directly. The one place presentation legitimately
> names a concrete adapter is the composition root — which is exactly what that
> permission exists for.

### Two distinct constraints, often conflated

"Framework-free domain" is not "dependency-free domain". A domain may reasonably
import a pure, stable library that expresses a **business** rule — an email
format validator, a money library — provided it performs no I/O. The question is
not "is this an external dependency?" but "does this dependency bring
infrastructure into the core?".

Also note: enabling deliverability checks in an email validator would resolve DNS
records — network I/O in the heart of the domain, making validity
non-deterministic. A value object validates a **form**, never a fact about the
outside world.

## What the rule buys, concretely

- **Testability** — domain rules test in microseconds, with no database or HTTP.
- **Replaceability** — swapping SQLite for PostgreSQL touches config, the engine
  and tests; zero lines of `domain/` or `application/`.
- **Reuse of use cases** — one `CreateUser` serves API, CLI and worker.
- **Readability** — the rules can be read without the plumbing around them.

The most reliable diagnostic of the whole architecture: **if your business rules
are hard to test, they are mixed with technical concerns.**
