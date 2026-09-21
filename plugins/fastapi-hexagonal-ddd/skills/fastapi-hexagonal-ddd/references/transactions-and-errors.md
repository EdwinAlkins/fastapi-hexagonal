# Transactions, errors and wiring

Three cross-cutting concerns. Each is handled once, in the right place.

## 1. The transaction boundary

Who decides `commit` / `rollback`? **Not the repository** — otherwise a use case
performing two writes could not make them atomic.

The formulation you often read — *"the transaction is the HTTP request"* — is
misleading: true of the API, false the moment a second channel exists. The right
one:

> **The transaction surrounds the use case.** Each driving adapter provides that
> boundary with the means of its channel.

```
Driving adapter (API · CLI · worker)
  └─ opens the transaction boundary
       └─ Use case
            └─ Repositories (mutate the session, never commit)
       └─ success → commit   |   failure → rollback + propagate
```

Three implementations of one principle:

```python
# API — one transaction per request
async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

```python
# CLI — one transaction per command
@asynccontextmanager
async def transactional_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

```python
# Worker — one transaction per message
async with session_factory() as session:
    use_case = NotifyTaskShared(...)
    try:
        await process_message(incoming, use_case, dlx)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
```

### What that buys, and what it is called

A use case can chain several writes in **one atomic transaction** without
knowing it. It knows no `commit`, no `rollback`, no session type — only ports.

This is a light form of **Unit of Work**. Other shapes are equally defensible: an
explicit Unit of Work passed to the use case, a `@transactional` decorator, a
transaction script. What matters is that the transactional responsibility be
**located and unique**, not the exact shape.

### Choosing when to commit

The three snippets above all commit inside the teardown of the boundary. For the
CLI and the worker that is unambiguous — the command or the message is finished.
For an HTTP request it is a real fork in the road.

| | **A. Commit before the response** | **B. Commit after the response** |
|---|---|---|
| Typical wiring | an explicit commit in the handler path, a middleware that commits, or a dependency scoped to end with the function | a `yield` dependency whose teardown runs post-response |
| A constraint violation at commit | propagates normally, your handlers map it | fires too late to change the status |
| Consequence | an opaque 500 unless translated | a **positive response for a rolled-back transaction** |
| Adapter must flush early? | yes — to *translate* the violation | yes — translation **and** the only way the client hears about it |

In FastAPI specifically, a dependency with `yield` runs its exit code *after*
the response is sent by default, which is strategy B. Since FastAPI documents a
`scope` parameter on `Depends`, `Depends(get_session, scope="function")` runs the
exit code right after the path operation function and **before** the response is
sent — that is strategy A. Check the behaviour of the version you are on rather
than assuming either.

### The verdict: for HTTP commands, prefer A

For `POST` / `PUT` / `PATCH` / `DELETE`, **commit before the response.** A `201`
or a `204` is a promise that the write is durable; strategy B can break that
promise silently, and no discipline in the adapters repairs it:

```
POST · PUT · PATCH · DELETE
  use case
    └─ flush where a constraint must be translated
  COMMIT
    └─ then build and send the 2xx
```

The reason the flush does not save you is that **a flush is not a commit**. It
surfaces the violations you anticipated, in the place that can translate them —
that is its job, and it remains worth doing under both strategies. But a
deferred constraint, a serialisation failure under `REPEATABLE READ`, a trigger,
a statement timeout or a dropped connection still fails at `COMMIT`, after every
flush succeeded. Only ordering the commit before the response makes a 2xx mean
"persisted".

Strategy B stays defensible for read-only paths and for writes whose
confirmation is explicitly advisory — a `202 Accepted` promises acceptance, not
durability. What it must never be is the default you did not choose. And note
that B is also the strategy under which the explicit `flush` stops being good
practice and becomes the only thing standing between a failed constraint and a
positive response.

### Limits to know

- **Non-transactional effects do not roll back.** An email sent or a message
  published inside the transaction is gone. See section 2.
- **There is no "after commit" inside the use case.** The boundary wraps it, so
  the use case returns *before* the commit. Anything that must run only once the
  data is persisted has to be hung on the boundary — which means the boundary has
  to be an object the use case can register with (an explicit `UnitOfWorkPort`, a
  request-scoped collector), not just a `yield` dependency. For an effect leaving
  the process, do not build that hook at all: write an outbox row inside the
  transaction. See the three cases in `events-and-messaging.md`.
- **Long transactions.** A boundary tied to a request holds while requests are
  short. A multi-minute job must be chunked, which means committing *during* the
  use case — requested explicitly through a `UnitOfWorkPort`, never obtained as a
  side effect of a repository. See `reads-and-writes.md`.
- **A commit failure can arrive too late.** Where the commit sits decides this,
  and there are two strategies. See *Choosing when to commit* above.
- **Infrastructure closes doors.** A connection pooler in transaction mode
  forbids anything that relies on session state surviving a transaction —
  `LISTEN`/`NOTIFY`, `WITH HOLD` cursors. Know your constraints before designing
  around them, and check them against your pooler's current version rather than
  against folklore (see `persistence.md`).

## 2. External effects: the dual-write problem

One business operation, two systems with no shared transaction:

```
"share a task"  =  write to the database   (PostgreSQL)
                +  publish a message       (RabbitMQ)
```

They cannot be made atomic. There are only two possible orders, and **both are
broken**:

| Order | What breaks | Result |
|---|---|---|
| Publish **then** commit | The commit fails after publishing | **Phantom** message: the consumer handles a row that does not exist |
| Commit **then** publish | The process dies in between | **Lost** message: the data is there, the effect never happened |

This is the *dual write problem*, and the key insight is that **no reordering
solves it**. Moving the publish only chooses which failure you prefer. You must
change mechanism.

For an email notification, preferring the phantom is usually right: a spurious
email is annoying, a silently unnotified share is worse. Say which you chose.

### The outbox

> Do not write to the broker — write to the database, **in the same transaction
> as the business data**.

```sql
CREATE TABLE outbox (
    id            uuid PRIMARY KEY,
    name          text        NOT NULL,   -- the event type
    payload       jsonb       NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    published_at  timestamptz              -- NULL until published
);
CREATE INDEX ON outbox (created_at) WHERE published_at IS NULL;
```

```python
async def execute(self, ...) -> None:
    task = await self._tasks.get(task_id)
    event = ShareTaskNotification(...)
    await self._outbox.add(event)      # same session, same transaction
```

A separate **relay** reads unpublished rows, sends them, and marks them
published.

### The cost the outbox moves — it does not remove it

Most write-ups skip this. The relay can die **after** publishing and **before**
marking the row. On restart it republishes.

> **On its own, an outbox does not give end-to-end exactly-once.** It gives
> *at-least-once* publication: "the message may be lost or phantom" becomes "the
> message will arrive, possibly more than once". That is an enormous improvement,
> but it makes **consumer idempotence mandatory**, not optional.

Adopting an outbox without making the consumer idempotent trades a silent loss
for silent duplicates. The problem was moved, not solved.

### Making a consumer idempotent

Idempotence is a property of the **processing**, not of the message. The test to
apply is:

> Delivering the same message N times must produce the **same observable
> outcome** and end in an **ack** — not merely "the database does not get more
> corrupted".

Three techniques, in order of preference:

**1. The operation is naturally idempotent** — the state transition is
convergent, so replaying it changes nothing.

```python
counter += 1                    # ❌ not idempotent
SET status = 'done'             # ✅ idempotent: converges
```

⚠️ **A guarded transition is not automatically an idempotent handler.** An
entity that raises on a second `complete()` protects its invariant — that is its
job — but if the handler lets that exception escape, the consumer nacks,
retries, and the message eventually lands in the dead-letter queue. The state is
correct and the pipeline says failure.

The handler must translate "already in the target state" into success:

```python
try:
    task.complete()
except TaskAlreadyCompleted:
    return                      # already done: this delivery is a no-op, ack it
```

Keep the two responsibilities apart: the **entity** refuses an illegal
transition; the **handler** decides that an already-reached state means this
particular message is done.

**2. A transactional inbox**, when processing only changes the same database as
the business data:

```python
async def handle(self, message_id: str, event: ShareTaskNotification) -> None:
    async with self._uow:
        try:
            await self._inbox.claim(message_id)    # INSERT, PK = message_id
        except AlreadyProcessed:
            return                                 # a committed delivery: ack
        await self._apply_database_changes(event)  # same transaction
```

The inbox record and the business changes **commit or roll back together**. A
crash before commit leaves no marker, so redelivery retries the work; a crash
after commit finds the key and acknowledges. The guarantee comes from the
transaction plus the uniqueness constraint, not from instruction ordering.

**3. An external effect.** PostgreSQL cannot atomically include an email or
payment provider. In the inbox transaction, write a **local outbox** describing
the effect; a separate worker delivers and retries it. If the provider supports
an idempotency key, pass `message_id` (or the outbox id). That closes the window
between "provider accepted the call" and "local completion was recorded".

Without provider-side idempotency, exactly-once is impossible: recording
`completed` before the call risks loss; recording it after risks duplication. A
`pending / processing / completed` state machine, leases, attempt counters and
reconciliation make the work observable and retryable, but they cannot invent a
guarantee the external system does not offer. For email, state explicitly which
risk is accepted.

**4. A business key rather than a message id.** Deduplicating on
`(task_id, user_id, day)` also protects against a legitimate republish after a
code change. More robust, harder to define.

> **A `processed` row alone is not a protocol.** Insert-and-commit before
> `_do_the_work()` can lose the work permanently: on redelivery, the row blocks
> the normal retry. Use inbox + database changes in one transaction, or inbox +
> outbox for an external effect. Otherwise the loss/duplication trade-off must be
> explicit.

### How the relay reads the outbox

| Mechanism | Latency | Cost | Note |
|---|---|---|---|
| **Polling** (`SELECT … WHERE published_at IS NULL`) | the interval | trivial | The default; the partial index is mandatory |
| **`LISTEN`/`NOTIFY`** | immediate | low | Unavailable behind a pooler in transaction mode |
| **CDC** (Debezium, logical replication) | near-immediate | high | One more component to operate; relevant at scale |

### Several aggregates in one operation

**In a monolith on one database**, changing two aggregates in one transaction
works with no special mechanism. It is an accepted deviation from "one aggregate
per transaction", perfectly tenable while the database is shared.

**Once the aggregates live in two services**, the shared transaction is gone:

| Approach | Principle | When |
|---|---|---|
| **Eventual consistency** | Each commits locally, an event propagates | The common case: a temporary gap is tolerable |
| **Saga** | A sequence of local steps, each with a compensation | When a late failure must undo earlier successes |

A saga does not replace an outbox — it needs reliable messaging to chain its
steps, so it **sits on top of one**. They answer different questions: the outbox
answers "how do I publish reliably?", the saga answers "how do I undo what
already succeeded?".

**2PC / XA** technically solves it and is avoided almost everywhere: modern
brokers support it poorly, it holds locks across systems, and a dead coordinator
leaves in-doubt transactions to resolve by hand.

### Do you actually need any of this?

Two questions decide, and neither is technical:

1. What happens if this message is **lost**?
2. What happens if it arrives **twice**?

| Loss | Duplicate | Answer |
|---|---|---|
| tolerable | tolerable | Direct publication |
| tolerable | unacceptable | Idempotent consumer, no outbox |
| unacceptable | tolerable | **Outbox** |
| unacceptable | unacceptable | **Outbox + idempotent consumer** |

A third option, often forgotten and sometimes the best: **periodic
reconciliation**. A nightly job comparing the two systems and repairing the gaps
costs far less than an outbox, and suffices when the correction latency is
acceptable.

## 3. Two families of errors

The domain raises **business exceptions** and knows nothing of HTTP. But not
everything is business: an unreachable database, an SMTP timeout, a dead broker
are **technical** failures. Conflating them means returning a 400 for a network
outage — telling the client their request was at fault.

Two parallel hierarchies:

```
Business — domain/shared/exceptions.py       Technical — application/shared/errors.py
  DomainError            → 400                 InfrastructureError
    ├─ ValidationError   → 422                   ├─ DependencyUnavailable → 503
    ├─ NotFoundError     → 404                   ├─ UpstreamTimeout       → 504
    └─ ConflictError     → 409                   └─ UpstreamBadResponse   → 502
```

The sorting criterion:

> **Can the client fix their request?** Yes → business error (4xx). No, a
> dependency is down → technical error (5xx).

> ⚠️ **Do not map the whole technical hierarchy to 503.** "Service temporarily
> unavailable" is a promise: retrying later may work. It is true of a dead
> broker; it is false of a bug in your own adapter. A `TypeError` in a mapper, a
> malformed query, a misconfiguration — those are **500**, and dressing them as
> 503 hides a real defect behind a transient-looking status, so nobody
> investigates and clients retry forever.
>
> Reserve the technical hierarchy for **genuine failures of an external
> dependency**, and let unexpected exceptions fall through to the default 500
> handler. If you only ever need one technical class, it is still worth naming it
> `DependencyUnavailable` rather than something that invites catching everything.
> The exact codes matter less than the distinction.

### Map the semantic bases, once

```python
@app.exception_handler(NotFoundError)
async def _not_found(_, exc): return _error(404, str(exc))

@app.exception_handler(ConflictError)
async def _conflict(_, exc): return _error(409, str(exc))

# + ValidationError → 422, DomainError → 400 (fallback)

@app.exception_handler(DependencyUnavailable)
async def _service_unavailable(_, exc):
    logger.error("Technical dependency unavailable: %s", exc, exc_info=exc)
    return _error(503, "A technical dependency is unavailable.")

# Anything not matched above is a bug: let it become a 500.
```

Four details that matter:

1. **A new context is covered without touching this file** — its exceptions
   inherit the right base, and the framework walks the class hierarchy to find
   the handler. The cost of adding a context stays constant.
2. **503 for an outage, 500 for a bug.** An unavailable external dependency is
   transient and external, not an anomaly of your service — but the reverse also
   holds: an anomaly of your service must not be reported as an outage.
3. **Log technical errors, not business ones.** A 404 is normal operation;
   logging it drowns the real incidents.
4. **Do not return technical detail to the client.** An infrastructure message
   may contain a host, a port, a trace. It stays in the logs.

Two disciplinary rules follow:

- **Never raise an HTTP exception outside `presentation/`.** Deciding the
  protocol from a layer that should not know it breaks the CLI and the worker
  immediately.
- **The domain does not log.** A logger is a side effect and a dependency; the
  domain should stay a pure function of its inputs. Logs belong to use cases and,
  above all, to adapters, where technical context actually exists.

And a corollary worth internalising: when a technical error reveals invalid
data — an SMTP failure caused by a malformed address — the fix goes at the
validation barrier, not in the error handler. That address should never have
reached the adapter.

## 4. The composition root

Somewhere, the abstract port must be bound to its implementation. That wiring
point is the **composition root**.

A common formulation to avoid: "the only place that knows both worlds". Taken
literally it is false — `SqlAlchemyTaskRepository` obviously knows both
`TaskRepository` (it implements it) and SQLAlchemy. What the composition root
uniquely holds is the **association decision**: "for this run, this port is
served by that adapter". That decision, and only it, must stay in one place —
otherwise it scatters into concrete imports and nothing is substitutable any
more.

```python
# dependencies/repositories.py — port ← adapter
def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)

# dependencies/task.py — use case ← its ports
def get_create_task(tasks: TaskRepositoryDep, users: UserRepositoryDep) -> CreateTask:
    return CreateTask(tasks, users)
```

Organise it deliberately: cross-cutting providers (session, repositories) in
their own modules, per-context providers in theirs, and **contexts never
importing each other**. Other projects put the composition root in a
`bootstrap/` or `container/` package at the root, which is preferable when
several driving adapters must share it. A CLI and a worker that build their
dependencies by hand is acceptable at small scale and becomes duplication to
watch as the number of wired use cases grows.

**This is also what makes tests easy**: substituting one adapter touches nothing
else. Integration tests replace the session dependency with an equivalent one
pointing at the test database, and inject an inert publisher instead of the
broker — the rest of the wiring stays authentic.
