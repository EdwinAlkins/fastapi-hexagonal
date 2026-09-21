# Cache, events and messaging

Two concerns that accompany the read path: not re-reading what you just read,
and telling others that something happened.

## The cache is an application decision

It belongs neither to the domain (no invariant depends on it) nor to
infrastructure alone (the use case decides what to cache) — hence a port in
`application/shared/cache.py`.

### Cache-aside

```
GetUser
  ├─ UserId.from_string(raw)        ← validate BEFORE anything
  ├─ cache.get("user:{id}")
  │    ├─ hit  → dict → UserDTO
  │    └─ miss → repository.get(id) → UserDTO → cache.set("user:{id}", …)
```

And the mandatory counterpart on every mutation:

```python
await self._cache.delete(f"user:{identity}")
```

### Three rules for a cache that does not become a bug

1. **The invalidation contract is written down** — in the use case docstring: the
   key is `user:{id}`, every mutation must delete it. A cache with no documented
   contract produces stale data nobody can explain.
2. **Invalidate rather than update.** Deletion is idempotent and much easier to
   reason about than rewriting the value, which can apply two mutations out of
   order. But **deletion is not race-free**, and claiming otherwise is a common
   error. Cache-aside has a repopulation race:

   ```
   reader                    writer
   GET cache → miss
   GET db    → old value
                             UPDATE db
                             DELETE cache
   SET cache → old value     ← stale value written AFTER the invalidation
   ```

   The stale entry now survives until its TTL. Mitigations, by increasing cost:
   **always set a TTL** so any stale entry is bounded; use single-flight so one
   reader repopulates; version the key (`user:{id}:v{n}`) so a mutation makes old
   entries unreachable rather than needing deletion; or take a short lock when
   the freshness guarantee genuinely requires it. Pick according to the staleness
   you can tolerate — and note that a TTL alone already turns an unbounded bug
   into a bounded one.
3. **The cache is never the source of truth.** Empty, cold or down, the
   application must still work — more slowly, that is all.

Watch derived keys: invalidating `user:{id}` but not `users:all` leaves the old
name in the list. Two strategies: explicitly invalidate every derived key on
mutation (simple, but the list of keys to remember grows and eventually gets
forgotten), or do not cache lists — or give them a short TTL and accept a
staleness window. In practice the second is often the right trade-off: lists are
cheap to recompute, and their invalidation is the main generator of cache bugs.

### Cache or query service?

Both answer the same symptom ("it is slow") by opposite means:

|  | Query service | Cache |
|---|---|---|
| What it changes | The **shape** of the query | The **number** of queries |
| Cost | One class to write | Coherence to manage |
| Risk | None (it is SQL) | Stale data |
| When | The query is badly shaped | The query is good but too frequent |

**The right query first, then the cache.** Caching an N+1 only hides it behind a
TTL — and the first cold cache brings it back at the worst possible moment, when
traffic resumes after a deploy or a restart. Once the query is fixed, ask again
whether the cache still buys anything. Often the answer is no.

A testing consequence usually discovered too late: a shared cache makes a suite
non-hermetic. Start a disposable instance for tests and flush it between tests.

## Events: what happens *afterwards*

Once something important has happened, other things often must follow: notify,
update a counter, audit. Slipping them into the use case slowly turns it into a
junk drawer coupled to the whole system.

### Domain event vs. integration event

Two different notions, frequently conflated:

|  | **Domain** event | **Integration** event |
|---|---|---|
| Emitted by | The aggregate itself | The application layer |
| Vocabulary | Internal to the context | Public, versioned contract |
| Scope | Within the process | To other services / contexts |
| Example | `TaskCompleted` | a `task.shared` message on a broker |

The pattern for a domain event:

```python
class Task:
    def complete(self) -> None:
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyCompleted()
        self.status = TaskStatus.DONE
        self.completed_at = _now()
        self._events.append(TaskCompleted(task_id=self.id, owner_id=self.owner_id))
```

The entity **records** the event; it sends nothing. That is what lets the domain
say "this happened" without ever knowing about emails, brokers, or any side
effect.

A project with a simple domain may legitimately have **no domain events at all**
and still have a real integration event. Do not add the first kind because the
second exists.

### Where the dispatch happens: three cases, three boundaries

The formulation that circulates — *"the use case collects the events after the
commit and dispatches them"* — does not hold here, and it is worth seeing why.
The transaction **surrounds** the use case (`transactions-and-errors.md`):

```
Driving adapter
  └─ transaction
       └─ use case
            └─ repositories
```

The use case returns *before* the commit. It therefore cannot run anything
"after the commit" — there is no such moment inside it. When the dispatch
happens is a property of the **boundary**, not of the use case. Three distinct
answers, and conflating them is where the design usually goes wrong:

**1. In-process handler, same transaction.** The handlers are part of the
operation: increment a counter, write an audit row, maintain a projection in the
same database.

```
aggregate → event → handler(s) → same session
──────────────────── COMMIT ────────────────────
```

The use case collects `pull_events()` and dispatches them itself, before
returning. Their writes join the transaction and roll back with it, and their
failure fails the operation — which is exactly the contract you want here, and
exactly the reason to put nothing non-transactional in this case.

**2. In-process notification, after commit.** The handler must run only if the
data was actually persisted, but its effect stays local and is allowed to be
best-effort: invalidate a cache entry, refresh an in-memory index.

```
use case → collects events → registers them with the boundary
boundary → COMMIT → dispatch
```

The use case still only *collects*; the **boundary** dispatches, because only
the boundary knows the commit succeeded. This is where the light "transaction in
the driving adapter" shape shows its limit: there is nowhere to hang "after
commit" unless the boundary is an object the use case can register with — an
explicit `UnitOfWorkPort`, a request-scoped collector. If you want case 2, you
have to build that object; it does not come for free with a `yield` dependency.

And it is still best-effort: the process can die between the commit and the
dispatch. Acceptable for a cache invalidation, not for anything a user or
another service is waiting on.

**3. Effect leaving the process: the outbox.** The recommended default for
anything crossing to RabbitMQ, an email provider or another service. The use
case translates the domain event into an **integration event** and writes it as
an outbox row, in the same session as the business data; a separate relay
publishes it.

```
use case → outbox row (same session)
──────────────────── COMMIT ────────────────────
relay → RabbitMQ
```

Note what this one does *not* need: an after-commit hook. That is precisely why
it is the robust option — the decision to publish is committed atomically with
the data, and delivery becomes a separate, restartable problem instead of a
window between two systems. See the outbox section of
`transactions-and-errors.md` for what it costs (at-least-once, hence mandatory
consumer idempotence).

The three vocabularies now sit in their right place:

| | Lives in | Crosses the process? | Mechanism |
|---|---|---|---|
| **Domain event** | the aggregate | no | direct dispatch, case 1 or 2 |
| **Integration event** | the application layer | yes | published, case 3 |
| **Outbox** | infrastructure | — | how case 3 stays transactional |

One rule joins them: **a domain event never goes on the wire as-is.** Publishing
it exports your internal vocabulary as a public contract you will then have to
version and keep. The translation domain event → integration event is the use
case's job, and it is not a formality.

### An integration event contract

```python
@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    name: ClassVar[str]            # the event TYPE, not a routing key

@dataclass(frozen=True, slots=True)
class ShareTaskNotification(IntegrationEvent):
    name: ClassVar[str] = "task.shared"
    task_id: str
    user_ids: list[str]
    subject: str
    body: str
```

```python
# application/task/use_cases/share_task.py
event = ShareTaskNotification(task_id=task_id, user_ids=user_ids, ...)
await self._message_adapter.publish(event)     # no serialisation, no routing
```

Serialisation and routing appear only in the adapter:

```python
body=orjson.dumps(asdict(event)),
routing_key=event.name,
```

`name` is a `ClassVar`, so it is not a dataclass field and does not enter the
published JSON. The wire message carries data only, which lets the consumer do
`ShareTaskNotification(**payload)` knowing nothing about the transport.

Note where the publication happens: in the **use case**, not in the domain. The
entity does not know a share can notify anyone — which is exactly why the domain
stays testable in microseconds.

The known limit of this direct publication: the message leaves **before** the
commit, so a failed commit leaves a phantom message behind. That is case 3
above, written the fast way; the outbox is how you fix it. See the dual-write
section of `transactions-and-errors.md`.

## Is a broker justified at all?

Careful with the symmetric, false conclusion: "if we tolerate losing the
message, let us call SMTP directly in the use case and drop the broker". These
are two distinct questions:

- **"Must the message be durable and transactional?"** → the outbox question.
- **"Must this work leave the HTTP request?"** → the broker question.

A broker is not there to guarantee delivery — misconfigured, it loses messages
perfectly well. It is there to **decouple the producer's rhythm from the
consumer's**, and the emitter from the list of listeners. Three situations make
it hard to replace.

**1. Smoothing load.** Sharing a task with 10 000 users is 10 000 emails. Without
a broker the HTTP request sends them itself: it holds a connection, an
application worker and a transaction for the whole operation, and opens as many
SMTP conversations as the provider tolerates before throttling — or blacklisting
the domain. With a broker the queue **is** the buffer: the producer writes one
message and returns; the consumer proceeds at its own pace. The lever is on the
consumer side, not the API:

```python
await channel.set_qos(prefetch_count=10)
```

That prefetch, and the number of workers, set the real throughput — not the
incoming traffic. A spike lengthens the queue; it does not take the API down.

**2. Recovering from failures without writing a retry engine.** The mail server
is down for two hours. Without a broker you need an `email_retry` table, an
attempt counter, a `next_attempt_at`, a cron sweeping it and concurrency
handling across instances. With a broker, redelivery and quarantine become queue
**configuration**:

```python
queue = await channel.declare_queue(
    "email_notifications",
    durable=True,
    arguments={"x-dead-letter-exchange": "email_notifications.dlx"},
)
```

One correction that circulates backwards: **RabbitMQ does not do exponential
backoff on its own.** A message rejected without requeue goes to the dead-letter
exchange, full stop. Growing delays are assembled: one waiting queue per tier
(`x-message-ttl` of 1 min, 5 min, 15 min) dead-lettering back to the main
exchange, or the delayed-message exchange plugin to hold the same in one place.
Two traps: per-message TTL expires in queue order (a 15-minute message blocks a
1-minute message behind it), and you need an attempt counter to avoid looping
forever — on a quorum queue, `x-delivery-limit` does that for you. Still far less
code than a homegrown retry table, but not free.

A dead-letter queue is often best left as a **terminus**: nothing consumes it, it
exists so a failure is visible rather than silent. Replay is an operations
gesture, not an automatic loop.

**3. One event, several consumers.** The case that really decides. If
`task.shared` must also feed an audit dashboard, push a webhook and sync a CRM,
the broker-less version means opening the use case and adding three calls —
coupling it to three third-party systems with their outages and latencies. With a
broker you do not touch the producer at all: three more queues bound to the same
exchange on the same routing key, each with its own pace, failures and
deployment.

> **That is what decoupling is:** not the number of components, but the number of
> files a new requirement forces you to reopen.

### When it is not justified

A broker is not neutral: a stateful component to deploy, monitor, secure and back
up, plus a second process to keep alive. If all three of these hold, it brings
nothing:

| Question | If the answer is… | Then |
|---|---|---|
| How many consumers? | **One**, and it will not change | The broker decouples nothing |
| How long does the work take? | **Milliseconds** | Doing it in the request is simpler |
| Are there spikes? | No, **steady and low** throughput | Nothing to smooth |

In that case a framework background task or an `asyncio` task is enough — with
its own accepted limit: the work dies with the process, so it is lost on the
first restart. Name that trade-off, and switch to the broker at the first of the
three signals to appear — typically the second consumer (analytics, CRM) coming
to hang off "a user was just created".

And if the need is merely to *catch up on discrepancies*, periodic reconciliation
costs less than either.

### Separating "consumed" from "all effects succeeded"

When a consumer partially succeeds — the email reached two recipients out of
three — the main message is still acknowledged, because it **was processed**;
replaying it would re-send to the recipients who already received it. The partial
failure is published separately (to the DLQ, with a reason), because an
acknowledged message is never dead-lettered. Without that explicit publish those
failures vanish silently.
