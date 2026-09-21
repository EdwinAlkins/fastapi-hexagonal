# Reads and bulk writes

Aggregates are designed to protect **writes**. This file covers the two places
where naive application of that design goes wrong: reading through aggregates,
and writing a hundred thousand rows through them.

## Part 1 — Reading without going through the domain

### The expensive misunderstanding

Having built a careful domain, a reflex sets in: **everything must go through
it**. True for writes. False for reads, and clinging to it produces systems that
are correct and unusable.

An aggregate is optimised for one thing: enforcing invariants at write time. That
requires assembling everything the invariants depend on and rebuilding the
business model, value objects included, before deciding anything. That contract
has a price, and the price buys nothing when you render a table: there is no
invariant to enforce.

|  | Write | Read |
|---|---|---|
| Goal | Protect invariants | Serve a screen, fast |
| Useful shape | A coherent aggregate | A flat projection |
| Granularity | The whole aggregate | Exactly the displayed fields |
| Crosses aggregate boundaries? | No — invariants are at stake | Yes — none are engaged |
| What counts | Correctness | Response time and database load |

### What reading through aggregates costs

A mundane screen: **50 tasks with their owner's name**.

```python
tasks = await task_repository.list(limit=50)          # 1 query
for task in tasks:
    user = await user_repository.get(task.owner_id)   # 50 queries  ← N+1
```

**51 queries** for four columns, plus a full rebuild of value objects that are
immediately converted back to strings.

Through a query service:

```sql
SELECT t.id, t.title, t.status, u.name AS owner_name
FROM tasks t JOIN users u ON u.id = t.owner_id
ORDER BY t.created_at DESC LIMIT 50;
```

**One query.** No aggregate built, no value object allocated.

Measured on a real PostgreSQL, 200 tasks across 10 owners:

| Path | SQL queries | Duration |
|---|---|---|
| Through aggregates (`list` then one `get` per task) | **201** | 84.6 ms |
| Through the query service | **1** | 6.6 ms |

> **The point is not that a page is slow.** A badly shaped read consumes
> connections and database CPU that then go missing for the **writes** — the very
> ones you worked so hard to make correct. A neglected read degrades the critical
> path.

It is also pernicious: invisible in development with ten rows, obvious in
production at 500 requests per second when the connection pool saturates.

### The move: dropping the domain, deliberately

On a read path you **deliberately abandon** entities and value objects,
invariants (nothing is being modified), aggregate separation (join freely), and
the repositories.

This is not a shameful exception — **it is the architecture working as
designed.** Invariants exist to prevent writing an incoherent state; a read
projection engages none. Paying for a protection that protects nothing here is a
design error, not evidence of rigour.

The corollary matters: it is not the word "read" that grants the shortcut. A read
that **decides a write** — loading a task in order to complete it — goes back
through the aggregate, because the decision does engage the invariants.

The rule that does not move:

> **A write that must enforce invariants goes through the model that carries
> them.** A query service is read-only, without exception: the day it writes, the
> invariants are worth nothing anywhere.

### Anatomy of a query service

Port, in `application/<ctx>/queries.py`:

```python
@dataclass(frozen=True, slots=True)
class TaskWithOwner:          # a READ DTO: flat, simple types
    task_id: str
    title: str
    status: str
    created_at: datetime
    owner_id: str
    owner_name: str
    owner_email: str


class TaskQueryPort(ABC):
    """READ path. No writes, without exception."""

    @abstractmethod
    def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]: ...
    @abstractmethod
    async def count(self) -> int: ...
```

Implementation, in `infrastructure/persistence/<ctx>/queries.py`:

```python
async def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]:
    statement = (
        select(TaskModel.id, TaskModel.title, TaskModel.status, TaskModel.created_at,
               UserModel.id.label("owner_id"),
               UserModel.name.label("owner_name"),
               UserModel.email.label("owner_email"))
        .join(UserModel, TaskModel.owner_id == UserModel.id)
        .order_by(TaskModel.created_at)
        .execution_options(yield_per=500)     # server-side cursor, constant memory
    )
    result = await self._session.stream(statement)
    async for row in result:
        yield TaskWithOwner(task_id=str(row.id), ...)
```

Five points of discipline:

- **The implementation lives in infrastructure**, like everything that speaks SQL.
- **It never returns entities**, only read DTOs — otherwise inter-aggregate
  navigation comes back through the side door.
- **It is read-only.** No `INSERT`, no `UPDATE`, ever.
- **It may cross several aggregate boundaries**, because it neither enforces nor
  modifies their invariants. The criterion is not "read = free, write = banned";
  it is *does this operation engage the invariants of the aggregates it touches?*
- **It is bounded, or it streams.** An unbounded read that materialises
  everything is an outage waiting to happen.

### No use case on the read path

The router calls the port **directly**. There is no business rule or
cross-aggregate coordination to orchestrate, so adding a use case would be an
empty indirection. The SQL adapter still owns a connection/session lifecycle and
normally runs inside an implicit database transaction; what is absent is a
business Unit of Work that intends to commit changes.

```
write:  router → use case → domain → repository     (4 levels)
read:   router → query service                       (2 levels)
```

The asymmetry is intentional: reads do not need the same guarantees, so they
should not pay the same ceremony.

### Streaming instead of paginating

An export can be streamed (NDJSON, one JSON object per line) with constant
memory — something the aggregate path structurally cannot offer, since it must
materialise everything before responding.

> ⚠️ **The price of streaming:** the HTTP status leaves with the first byte. If
> the database dies mid-stream you can no longer return a 500 — the client gets a
> truncated body with `200 OK`. Validate a streamed export by comparing the
> number of received lines to an announced count, never by trusting the status
> code.

One non-obvious mechanic worth verifying in your own framework: with a streaming
response, the `yield`-based dependency providing the session stays **open for the
whole body consumption**. Without that property, the cursor would close before
the stream ends. The cursor then lives *inside* the request transaction, which
stays compatible with a pooler in transaction mode — only `WITH HOLD` cursors,
which survive the commit, are forbidden there.

### Does a query service need a port?

Both schools are defensible.

|  | No port | With a port |
|---|---|---|
| The router depends on | the concrete infrastructure class | an interface in `application/` |
| Ceremony | minimal | one more interface |
| Testing the router | requires a real database | an in-memory double is possible |

Choosing the port keeps the dependency rule uniform and verifiable, which is
worth something if the rest of the codebase is uniform. Skipping it is perfectly
legitimate elsewhere: a query service *is* already the read model, and abstracting
it sometimes buys nothing.

### When to switch

| Situation | Path |
|---|---|
| Write that must protect domain invariants | **The model that owns those invariants** (usually an aggregate) |
| Mechanical write with no domain invariant | A narrower application/infrastructure path may be legitimate; state why |
| Load an object **in order to modify it** | **Aggregates** (invariants needed) |
| Display one object, a few fields | Aggregates — the cost is negligible |
| Display a **list** | Query service once the list is long or frequent |
| Display data from **two aggregates** | **Query service** |
| Count, aggregate, compute statistics | **Query service** (`COUNT`, `GROUP BY` — never in Python) |
| Export, feed a report | **Query service** |

The most reliable signal: **you are writing a Python loop that redoes what a
`JOIN` or a `GROUP BY` would do better.**

### Query service ≠ CQRS

Adding a read service is a good local practice. **CQRS**, in the strong sense, is
**two distinct models** — sometimes two databases, fed by projections, with
eventual consistency between them. It is a heavy architecture justified by
scalability needs or a massive read/write asymmetry.

There is a continuum, and you should know where you sit:

```
1. Everything through the aggregates          ← the starting point
2. + query services for reads                 ← where most projects belong
3. + denormalised read models                 ← "light" CQRS
4. + a separate, projected read store         ← full CQRS
5. + events as the source of truth            ← Event Sourcing (another subject)
```

The vast majority of applications stop at **level 2** and are right to. It is the
best benefit/cost ratio on the list: a few read classes, no extra
infrastructure, no eventual consistency to manage. Going one step up must answer
a **measured** problem, not an urge.

And within level 2, migrate only what justifies it. Simple list endpoints that
join nothing have no N+1 and can stay on the aggregate path. Leaving residual
waste — rebuilding aggregates to convert them straight into output DTOs — is a
legitimate, invisible cost at that scale. **You do not migrate everything to
level 2 because you understood level 2.**

## Part 2 — Writing in bulk without breaking the domain

### The asymmetry that governs everything

|  | Read | Write |
|---|---|---|
| What aggregates protect | nothing — you are only looking | the model's invariants |
| Can you short-circuit them? | **yes**, it is the right usage | **no**, never |
| What you optimise | the query itself | the **transport** to the database |

A query service may drop the domain because a projection engages no invariant. An
import may not: it introduces states you will have to answer for. What you may
optimise is how those states reach the database — not the verification that they
are valid.

### The trap: `create()` cannot represent the existing

```python
@classmethod
def create(cls, *, owner_id, title, description=None) -> Task:
    return cls(
        id=TaskId.generate(),      # ← a NEW identifier
        status=TaskStatus.TODO,    # ← necessarily TODO
        created_at=_now(),         # ← necessarily now
        completed_at=None,
    )
```

An import carries an existing `task_id`, a `status` that may be `done`, a
three-month-old `created_at` and a `completed_at`. Importing via the create use
case then calling `complete()` produces **three silent corruptions**: a new
identifier (so the original reference is lost and the import is no longer
replayable), a rewritten creation date, a wrong completion date.

You would feel rigorous, *since you went through the business layer*, while
destroying the data. That bug only shows up at reconciliation, six months later.

### Reconstituting is not bypassing

The right entry point is **`reconstitute()`** — for imports and for the
persistence mapper. Validation does not disappear: it builds the value objects,
so an empty title is rejected regardless of provenance.

> `create()` plus the transitions answer *"is this state reachable?"*
> `reconstitute()` plus the value objects answer *"is this state valid?"*

For entities that already existed elsewhere, the second question is the right
one. The first is actively harmful: it would reject a completed task on the
grounds that one cannot be *born* completed.

What reconstitution does not replay are the **transition** rules — consistent,
since they concern changes of state and have no meaning for a state at rest.

A bulk writer **does not go through the repository** — it writes in one grouped
statement — but it does go through the model that carries the invariants. Not an
exception to the rule: the rule stated at the right level. What you never bypass
is the **model**; the persistence path is negotiable.

### The gap value objects cannot see

A value object validates **one** field. It can say nothing about an inconsistency
*between* fields: `status = "todo"` with a populated `completed_at` sails
through. That is an invariant of the **entity**, so put it there:

```python
@classmethod
def reconstitute(cls, *, id, owner_id, title, description, status,
                 created_at, completed_at) -> Task:
    if status is TaskStatus.DONE and completed_at is None:
        raise InconsistentTaskState("a completed task must carry a completion date")
    if status is not TaskStatus.DONE and completed_at is not None:
        raise InconsistentTaskState("an unfinished task cannot carry a completion date")
    if completed_at is not None and completed_at < created_at:
        raise InconsistentTaskState("completion precedes creation")
    return cls(...)
```

`reconstitute` checks **all intrinsic state invariants**, regardless of
provenance. The SQLAlchemy mapper calls it too: an older application version, a
bad migration, raw SQL or manual intervention can make the database
inconsistent. CSV-specific checks may still run before this method; they are
additional input validation, not weaker domain invariants.

Keeping them separate also preserves the **intention**: `Task(...)` does not say
whether you are creating or re-reading, whereas the name `reconstitute` signals
that identity and dates come from outside.

### Where the time actually goes

Not in the domain. Building 100 000 aggregates with their value objects is pure
CPU — on the order of a second. The cost is in the round trips:

| Step | Cost per row |
|---|---|
| use case → `users.exists(owner_id)` | 1 `SELECT` |
| `repository.save()` → `session.get(Model, id)` | 1 `SELECT` |
| flush | 1 `INSERT` |

**Three round trips per row** — 300 000 queries for 100 000 tasks. The N+1 seen
from the write side.

> **Keep the domain in memory; batch the I/O.**

Measured round trip on 2 000 tasks across 50 owners:

| Path | SQL queries |
|---|---|
| Row by row through the create use case | **6 000** (2 000 `INSERT` + 4 000 `SELECT`) |
| Batched import (batches of 1 000) | **5** (4 `INSERT` + 1 `SELECT`) |

Replaying the same file inserts **0** rows.

### The optimisation ladder

| # | Move | Effect |
|---|---|---|
| 1 | Drop the per-row existence check | N `SELECT` → 0 or 1 per batch |
| 2 | Drop read-before-write: on import you know you are inserting | N `SELECT` → 0 |
| 3 | Multi-row `INSERT` per batch | N `INSERT` → N/1000 |
| 4 | Very large volumes: `COPY` into a staging table, then `INSERT … SELECT` | ~5–10× on insertion |

A design choice from earlier pays off decisively here: **identities generated by
the domain**. The whole batch is built in memory before touching the database —
no `RETURNING`, no round trip to learn an identifier.

### `ON CONFLICT` and its limit

Batched insertion relies on `ON CONFLICT DO NOTHING`: an identity already present
is skipped rather than overwritten or raised. That is what makes the import
**idempotent**, therefore resumable.

> ⚠️ **`ON CONFLICT` absorbs uniqueness conflicts. It does not absorb foreign-key
> violations.**

The nuance looks technical; it is structural. If a user in the file carries an
email already held by a **different** identity, that user is skipped — and their
tasks then violate the foreign key, which fails the **entire** `INSERT`. One
dubious row takes 999 others with it. So you still need to know who actually got
in: one query per **batch**, and only when a parent was skipped.

This is a case where intuition ("`DO NOTHING` will absorb everything") is wrong,
and only execution against a real PostgreSQL says so.

### Neither one transaction per row nor one for everything

A single ten-minute transaction is a **defect**, not a guarantee:

- behind a pooler in transaction mode it pins a server connection for its whole
  duration — on a pool of 20, that is 5 % of capacity removed;
- the WAL grows, dead tuples accumulate;
- a failure at 99 % loses the 99 %.

So you chunk, which means committing **during** the use case. Expressed as a
need, i.e. as a port:

```python
class UnitOfWorkPort(ABC):
    """Makes durable everything written since the last acquisition point."""
    @abstractmethod
    async def commit(self) -> None: ...
```

Three cautions:

- **It is not Fowler's full Unit of Work**, which tracks modified objects and
  decides what to write. The ORM session already does that; the port exposes only
  the **acquisition point**.
- **It does not make committing casual.** It should be the only thing outside
  driving adapters that commits, and a use case must **ask for it explicitly** in
  its constructor. You never get it as a side effect of a repository.
- **It is justified by duration, not volume.** A use case answering an HTTP
  request has no reason to take it: its transaction is already the right size.

You trade global atomicity for **resumability** — acceptable only because the
writes are idempotent. The two decisions hold each other up: without idempotence
a non-atomic import is unmanageable; without chunking, idempotence is pointless.

### Return a report, not a verdict

At 100 000 rows, all-or-nothing is a bad contract. Return a summary: rows read,
inserted, already present, **rejected with the reason**.

This is the least obvious argument in favour of the domain in an import. A raw
`COPY` returns an opaque database error at row 47 231 and stops. The domain can
say:

```
row 47231 (01930000-…): Invalid email address: 'ada@@example.com'.
```

Business exceptions do not only protect the database — they make failure
**diagnosable**. That is often the benefit that convinces.

Watch what accumulates across batches, though: an unbounded rejection list and a
global "already seen" identity set both grow with the file. Five million UUIDs
are hundreds of MiB. Bound the retained rejections, and consider delegating
deduplication to `ON CONFLICT` — you lose the distinction between "duplicate in
the file" and "already in the database", you gain constant memory.

### Restoring is not importing

The most expensive trap is not poor optimisation — it is picking the wrong
category. Decide before writing a line.

|  | Restore | Import |
|---|---|---|
| Where the data comes from | the same system, same version | elsewhere, or an edited file |
| Was the state already valid here? | yes | unknown |
| The right tool | `pg_dump` / `pg_restore` | the domain |

Routing a restore through the business layer is slower, more fragile and buys
nothing: you revalidate data you produced yourself. Conversely, importing foreign
data through `pg_restore` forfeits every guarantee.

Ask it **before** all the engineering above: *do I even need an import?* The
answer is often no, and it then saves a use case, two ports, two adapters and
their tests. The best import code is the one you do not write.

### Give the exchange format its own life

Reusing an export read DTO as the import format is a tempting shortcut and a
critiquable one: a read model is drawn for a screen. Binding it to the import
path means the day you add a display column, you change the exchange format
without noticing — and the coupling runs both ways. Adding a field to the read
DTO *only* so the import round-trips faithfully means the read model now carries
a column no screen displays.

It also bites immediately if the API streams NDJSON while a client saves a JSON
array: two formats for the same data, neither specified anywhere, and the first
file downloaded from the UI turns out to be unimportable by the CLI of the same
project.

A real transfer between deployments deserves its **own, versioned** format,
decoupled from what the screen displays.

### Updates are not insertions

Switching `DO NOTHING` to `DO UPDATE` writes directly into an aggregate's row
**without going through its transitions** — you could drag a `done` task back to
`todo`, which `complete()` exists to forbid. A grouped `INSERT` is acceptable
because an insertion crosses no transition; an update does.

Either keep the import insert-only and route modifications through the normal
write path (load the aggregate, apply the transition, save), or — if bulk update
is a genuine need — model it as an explicit business operation with its own rules
about what is allowed to change.
