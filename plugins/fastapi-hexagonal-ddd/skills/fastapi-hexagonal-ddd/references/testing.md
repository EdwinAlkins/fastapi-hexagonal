# Testing and automated guard rails

## Three levels, not two

The intermediate level is the one most often forgotten, and it is the one this
architecture exists to make possible.

```
Integration  — HTTP → use case → domain → real engines        (seconds)
Use cases    — use case + in-memory ports (hand-written fakes) (milliseconds)
Domain       — entities, value objects, invariants, zero I/O   (microseconds)
```

### 1. The domain: pure and instant

No database, no HTTP, no mocks. Just objects.

```python
def test_complete_twice_is_rejected() -> None:
    task = Task.create(owner_id=UserId.generate(), title=TaskTitle("x"))
    task.complete()
    with pytest.raises(TaskAlreadyCompleted):
        task.complete()
```

This is *possible and easy* precisely because the domain depends on no
framework. **If your business rules are hard to test, they are mixed with
technical concerns** — the single most reliable judge of the whole architecture.

### 2. Use cases: ports doubled in memory

This level tests the **orchestration**: branches, error cases, interactions
between ports — with no I/O.

```python
class FakeTaskRepository(TaskRepository):
    def __init__(self, tasks: list[Task] | None = None) -> None:
        self._by_id: dict[TaskId, Task] = {t.id: t for t in (tasks or [])}
        self.saved: list[Task] = []

    async def save(self, task: Task) -> None:
        self._by_id[task.id] = task
        self.saved.append(task)          # recorded so it can be asserted on

    async def get(self, task_id: TaskId) -> Task:
        try:
            return self._by_id[task_id]
        except KeyError:
            raise TaskNotFound(str(task_id)) from None
```

```python
async def test_create_task_rejects_unknown_owner() -> None:
    use_case = CreateTask(FakeTaskRepository(), FakeUserRepository())
    with pytest.raises(UserNotFound):
        await use_case.execute(CreateTaskCommand(owner_id=str(UserId.generate()), title="x"))
```

This level exists **only** because use cases depend on ports alone. Fakes worth
writing alongside repositories: a fake cache (to test hit/miss without a cache
server), a recording publisher (to assert a message was published without a
broker), a fake mail sender (to test a partial send failure without an SMTP
server).

**Prefer hand-written doubles to generic mocks.** A `FakeTaskRepository` that
really implements the port fails type checking when the port changes; a
`Mock()` keeps passing while lying.

Type compatibility is necessary, not sufficient. Run the same **contract test
suite** against every repository adapter and its in-memory fake. The shared
suite should pin observable semantics: not-found behaviour, uniqueness,
ordering, pagination boundaries, save/update identity and delete semantics. A
fake that has the right method signatures but returns a different order or
silently upserts when PostgreSQL rejects a duplicate is not a faithful test
double.

Keep engine-specific tests as well: the contract proves parity, while PostgreSQL
integration tests prove constraints, isolation and driver behaviour.

### 3. Integration: the real engines

Exercise the whole chain — HTTP → use case → domain → database — against
**disposable real engines** (testcontainers or equivalent).

```python
@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()
```

**Why real engines rather than an in-memory substitute?** A test passing on a
dialect production never uses proves very little. Here you genuinely exercise the
native `uuid` type, `timestamptz`, uniqueness violations, `ON DELETE CASCADE` and
the cache protocol. The price: a few seconds at suite startup, and a container
runtime as a hard requirement.

Containers also make the suite **hermetic**. Without them, a cache server
listening on the machine's default port — typically the project's own dev stack —
gets used by the tests, which then read entries left by a previous run.

**What the client fixture substitutes, exactly.** Mount the **real** application
(routers, DI, genuine error handlers) and override two things only:

- the session dependency → an equivalent one (same `commit`/`rollback` semantics)
  pointing at the test database. Reproducing the real transaction boundary is not
  decorative symmetry: a fixture that always committed, with no `try/except`,
  would stop proving that errors trigger a **rollback** — and a test asserting
  that a failed create leaves no stray row would prove nothing.
- the messaging adapter → an inert publisher, so no real broker is needed.

The rest of the wiring is production wiring. The composition root is what makes
that substitution surgical.

### Two choices to make deliberately

**Isolation strategy.** Pick according to suite size and what you are testing —
there is no single right answer:

| Strategy | Isolation | Cost | Fits |
|---|---|---|---|
| Roll back a transaction per test | good | lowest | large suites; breaks if the code under test commits |
| Truncate tables between tests | good | low | most suites |
| Create/drop the schema per test | total | high | small suites, or schema-sensitive tests |
| One database per test | total | highest | parallel suites |
| One container per suite | — | amortised | combine with any of the above |

Schema-per-test buys order-independence at a cost that becomes the dominant term
in a large suite. Start cheap and tighten when flakiness appears.

**How to build the starting state.** Prefer going through the domain or the use
cases: a raw `INSERT` can create a state the business code would never produce —
an empty title, a `completed_at` on a `TODO` task, a non-normalised email — and
the test then validates an impossible situation, or worse, "proves" behaviour for
data that cannot exist.

Direct persistence setup is nevertheless legitimate when:

- you are testing the repository or the mapper **itself**;
- you deliberately need a **pathological** row (legacy data, a state predating a
  migration) to check that reading it fails loudly;
- going through the use cases would make setup dominate the test, and the state
  is provably reachable anyway.

The rule is not "never raw SQL". It is: **do not accidentally test an
unreachable state.**

## Where does each test go?

| What you are testing | Level |
|---|---|
| An invariant, a validation, a state transition | Domain |
| An orchestration, an error branch, a cache hit/miss | Use case (fakes) |
| A full journey, an HTTP status, a SQL constraint, engine behaviour | Integration |

The guiding principle: **test each thing at the lowest level that can prove
it.** Asserting "empty title rejected" in an integration test when a domain test
already covers it adds seconds of suite time for little information.

"Little", not "zero" — a thin integration test that the rule is actually *wired*
(that the API surfaces a 422 rather than a 500) tests something different from
the rule itself, and is worth having once. What you want to avoid is
re-testing the same *logic* at several levels, not every overlap.

Do not copy anyone's ratio. The distribution is whatever that principle produces
for *your* domain. A richer domain grows the base; an anemic domain makes the
base disappear — which is the real alarm signal.

### Pinning query counts

Counting the statements a code path emits — by subscribing to the ORM's
cursor-execution event — is a cheap, high-value regression test for read paths
that matter: it catches the day someone reintroduces an N+1 that no functional
assertion would notice.

Pin the count on paths you **care about keeping fast**. Do not pin it everywhere:
a query-count assertion is coupled to the ORM's emission strategy and will break
on legitimate refactors, so it costs maintenance wherever it does not protect
something real.

One variant worth calling out as **pedagogical only**: deliberately keeping a
known-N+1 implementation alongside the good one and pinning *its* `1 + N` count,
so a comparison in teaching material cannot silently go stale. That is a
reasonable thing for a reference repository to do and a bad thing to copy into a
product — there, you delete the slow path instead of testing it.

## Automated guard rails

```bash
make lint     # linter + import contracts + strict type checking
make test     # the three levels
make check    # = lint + test, reproduces CI locally
```

Run the import contracts in **pre-commit and CI**, not only locally. An
architecture rule that is not verified degrades within months — see
`architecture.md` for the contract definitions.

Useful additions: strict type checking (it catches a fake drifting from its
port), and a lint rule against private-member access from outside
(Ruff `SLF001`), which closes the `entity._state = X` back door once entities
expose read-only properties.

## Review checklist

Before calling it clean:

- [ ] The architecture check passes — not just a `grep`.
- [ ] Entities change state through **methods**, never bare attribute assignment.
- [ ] Value objects validate **a form**, with no I/O.
- [ ] Every aggregate has a **justifiable boundary**: which invariant motivates it?
- [ ] Aggregates reference each other **by identity**; inside one, objects
      reference each other normally.
- [ ] Repositories **do not commit**; the transaction surrounds the use case.
- [ ] The domain raises **business exceptions**; technical errors have their own
      hierarchy and their own status codes (5xx).
- [ ] No HTTP exception, no logger, no framework inside the domain.
- [ ] Use cases are testable **without** a database or HTTP.
- [ ] Each port sits in the layer that **expresses the need**.
- [ ] Every cache has a **written invalidation contract**.
- [ ] A new context means **new files**, not scattered edits.
- [ ] Read paths that join two aggregates go through a query service, not a loop.
- [ ] Bulk writes go through the model but not necessarily through the repository.

## The most frequent mistakes

- **Anemic model**: entities with no behaviour, all logic in use cases or routers.
  The domain then does not really exist.
- **Merging entity and ORM model**: the domain starts depending on the ORM.
- **Committing inside a repository**: breaks multi-write atomicity.
- **Navigating between aggregates** (`user.tasks`) instead of querying by identity.
- **Believing DDD forbids collections**: inside an aggregate they are normal.
- **Putting everything in services**: the anemic model in disguise.
- **Filing every error under the domain hierarchy**: a broker outage is not a
  business problem.
- **Confusing a query service with CQRS.**
- **Over-splitting**: applying a pattern (a façade, subfolders) everywhere by
  reflex. Splitting must serve readability, case by case.
- **Postponing the automated dependency check.**
