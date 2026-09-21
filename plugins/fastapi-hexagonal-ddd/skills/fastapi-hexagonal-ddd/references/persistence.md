# Persistence adapters

An adapter **translates**; it does not decide. It contains no business
invariant. It may contain rich *technical* logic (retries, dead-lettering,
batching) — never business logic.

## The ORM model is not the domain entity

The constant temptation is to use one class for both. Separating them has a
**real cost** — two classes to maintain, a mapper to write, one more test when a
field is added. Be honest about it rather than denying it. What it buys:

- the domain does not import the ORM — otherwise the "framework-free domain"
  contract fails, and, more importantly, testing a rule would require a database
  engine;
- database constraints (column types, nullability, cascades) do not bleed into
  the business model;
- the entity can be **richer** than its table: encapsulation, value objects,
  invariants, factories — things a declarative ORM model expresses badly;
- a schema migration does not touch the domain.

If the domain is a CRUD with no rules, that cost buys nothing. That is one of the
clearest signals the architecture is oversized.

```python
class TaskModel(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
```

## Mappers

A mapper converts entity ↔ model. It is the only place that knows both shapes.

```python
def to_domain(model: TaskModel) -> Task:          # ORM → domain
    return Task.reconstitute(
        id=TaskId(model.id),
        owner_id=UserId(model.owner_id),
        title=TaskTitle(model.title),
        # …
    )

def to_model(task: Task) -> TaskModel:            # domain → ORM
    return TaskModel(id=task.id.value, owner_id=task.owner_id.value, ...)
```

`to_domain` uses **`reconstitute()`**, not the `create()` factory. Rebuilding an
existing task is not creating a new one: you want neither a regenerated identity
nor a reset `created_at`, and you do want every intrinsic state invariant checked.

Note a desirable consequence: if a row was inserted by a raw SQL script with an
empty title, `to_domain` raises a business error on read. That is not a mapper
bug — it is the system reporting that the database holds a state the domain
considers impossible. The real bug is upstream; the structural fix is a `CHECK`
constraint.

## Repositories

```python
class SqlAlchemyTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session          # session INJECTED, never created here

    async def get(self, task_id: TaskId) -> Task:
        model = await self._session.get(TaskModel, task_id.value)
        if model is None:
            raise TaskNotFound(str(task_id))    # business error, not None
        return mappers.to_domain(model)
```

Three rules of conduct:

1. **It does not create its session, it receives one.** Otherwise two
   repositories in the same use case would work in two different transactions.
2. **It does not commit.** The transaction boundary is elsewhere
   (`transactions-and-errors.md`). A `commit()` added "to be safe" inside `save()`
   breaks atomicity across multiple writes — and in a message consumer it means a
   later failure leaves the database modified while the message is rejected and
   replayed: partial effects, replayed. The worst of both worlds.
3. **It translates absences into business errors.** `get` raises `TaskNotFound`;
   `exists` returns a boolean for callers who want to test.

### Translating constraint violations

Where a constraint can fire, the repository forces a `flush` and converts the
driver error into the business one:

```python
async def save(self, user: User) -> None:
    self._session.add(mappers.to_model(user))
    try:
        await self._session.flush()
    except IntegrityError as exc:
        if _is_unique_violation(exc, "users_email_key"):
            raise EmailAlreadyUsed(str(user.email)) from exc
        raise
```

Two distinct reasons justify that flush, and they are worth keeping apart
because only one of them depends on where the commit sits:

1. **Translation** — it makes the driver error surface *here*, in the one place
   that knows which constraint was violated and which business error it maps to.
   Without it, the `IntegrityError` escapes from wherever the commit happens,
   with no context left to translate it: an opaque 500, at best. This reason
   holds under every commit strategy.
2. **Timing** — and this one applies only under **commit-after-response**
   (strategy B in `transactions-and-errors.md`). If the commit runs in a teardown
   that executes once the response has been sent, the violation fires too late to
   change the status, and the client receives a complete, positive response for a
   rolled-back transaction. Under commit-before-response the commit itself would
   have caught it, so there reason 1 is the one doing the work.

So the rule stays unconditional — but do not mistake what it buys. **A flush is
not a commit.** Deferred constraints, a serialisation failure, a trigger, a
dropped connection can all still fail at commit time, after a successful flush.
Flushing early makes the *expected* violations translatable; only committing
before you answer makes a 2xx mean "persisted".

## SQLAlchemy pitfalls worth knowing

- **Cross-file relationships.** `TaskModel.owner` ↔ `UserModel.tasks` resolve by
  *class name* through the SQLAlchemy registry: import the target model only
  under `TYPE_CHECKING`, and have `init_db` import both `models` modules so they
  register. The foreign key itself references the table by string (`"users.id"`)
  and needs no import at all.
- **Do not shadow the `list` builtin.** A method named `list()` on a class makes
  every `list[T]` annotation written *after it* resolve to the method (a mypy
  error). Prefer an intention-revealing query name such as `list_page` on a query
  port; otherwise use `builtins.list` in annotations or order methods carefully.
- **Implicit attribute-triggered lazy loading is problematic in async.** A plain
  relationship access cannot silently perform arbitrary I/O; use eager loading
  such as `selectinload`, explicit refreshes, or SQLAlchemy's documented
  `AsyncAttrs` mechanisms when truly needed. For read views, explicit eager
  loading remains the clearest default. The `relationship` lives in ORM models,
  not the domain.
- **A connection pooler in transaction mode** (PgBouncer and friends) removes
  anything that assumes session state survives a transaction: no
  `LISTEN`/`NOTIFY`, no `WITH HOLD` cursors, no session-level `SET` or advisory
  locks you expect to outlive the transaction.

  **Prepared statements are no longer part of that list by default.** PgBouncer
  gained named prepared-statement tracking in transaction mode in 1.21 via
  `max_prepared_statements`. Whether it works still depends on your driver and
  its configuration, so disabling statement caching remains a **compatibility
  fallback, not a universal requirement**. Verify against the versions you
  actually run rather than repeating an older rule of thumb.

  This is a good example of an infrastructure constraint that is real, dated, and
  worth re-checking — not an architectural law.

## Driving adapters

The most convincing demonstration of the architecture: the same use case served
by several entry points, with no adaptation.

### HTTP

Transport schemas are the **contract of the channel**. This is exactly where
Pydantic belongs.

```python
class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = None


@router.post("/{user_id}/tasks", status_code=201)
async def create_task_for_user(
    user_id: str,
    payload: CreateTaskRequest,
    use_case: Annotated[CreateTask, Depends(get_create_task)],
) -> TaskResponse:
    dto = await use_case.execute(
        CreateTaskCommand(owner_id=user_id, title=payload.title,
                          description=payload.description)
    )
    return TaskResponse.from_dto(dto)
```

No business `if`, no database access, no `try/except` on domain errors — those
are handled globally.

### CLI

```python
async def _create_user(name: str, email: str) -> None:
    async with transactional_session() as session:
        use_case = CreateUser(repository=SqlAlchemyUserRepository(session))
        result = await use_case.execute(CreateUserCommand(name=name, email=email))
    click.echo(f"User created: {result.id}")
```

Same use case, same domain, same rules. What differs: the CLI builds its own
dependencies and provides **its own** transaction boundary. That is the proof, in
eight lines, that the business logic never depended on HTTP.

### Worker / consumer

A driving adapter triggered by a message rather than a human. It shows two things
HTTP does not: **one transaction per message**, and failure handling specific to
the channel — dead-lettering, retry policy, partial-failure reporting. That logic
is purely adapter-level; neither the use case nor the domain knows about it.

## Two validations, two roles — do not conflate them

The `min_length=1` on the HTTP schema and the `EmptyTitle` in the value object
are not the same thing:

|  | Transport schema | Value object |
|---|---|---|
| Role | Filter the channel, produce a clean 422 | Guarantee the business invariant |
| Scope | HTTP callers | **Every** caller: API, CLI, worker, tests |
| Can it be removed? | Yes, the error just gets uglier | No, the rule would disappear |

The **source of truth is the domain**; the schema is an ergonomic filter at the
façade. The limiting case proves it:

```python
{"title": "   "}     # passes min_length=1 (three characters!) → rejected by TaskTitle
```

Not faulty duplication: two guard rails at two altitudes. The sign it is healthy
is that the **constant is shared**, not copy-pasted — when the limit changes, one
place moves (plus a migration).
