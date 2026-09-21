---
name: fastapi-hexagonal-ddd
description: Design, review, refactor or extend Python/FastAPI backends with hexagonal architecture (ports & adapters) and tactical DDD — layered domain/application/infrastructure/presentation code, entities, value objects, aggregates, use cases, repositories, mappers, query services, transaction boundaries and enforceable import rules. Use when deciding where a business rule belongs, choosing an aggregate boundary, adding a port or an adapter, auditing layer violations, or scaffolding such a backend. Do not use to mechanically add DDD or hexagonal layers to a thin CRUD, a script, an ETL or a throwaway prototype, where the indirection buys nothing.
---

# FastAPI Hexagonal Architecture & Tactical DDD

Apply hexagonal architecture and tactical DDD pragmatically to Python/FastAPI
backends.

The goal is **not** to reproduce a template. It is to give every kind of
decision a home, so business rules stay explicit, testable and independent of
frameworks — and to recognise the projects where that costs more than it pays.

The user's requirements always win over this skill.

## The one rule

> Dependencies point **inward**. The core knows no concrete implementation of
> the outside world.

The core does not *ignore* external needs — it **declares** them as interfaces
(**ports**) without knowing who fulfils them. That is dependency inversion: the
need is owned by whoever expresses it, not by whoever satisfies it.

The **flow of control and of imports** looks like this:

```
presentation ──────► application ──────► domain
(driving adapters)         ▲                ▲
                           │                │
infrastructure ────────────┴────────────────┘
(driven adapters: they IMPLEMENT the ports declared above)

composition root ─► the only place that names concrete implementations
```

| Layer | Holds | Imports |
|---|---|---|
| `domain/` | entities, value objects, aggregates, domain exceptions, business-owned ports; this template also places aggregate repositories here | nothing framework-shaped |
| `application/` | use cases, DTOs, technical ports | `domain/` |
| `infrastructure/` | driven adapters: ORM, cache, broker, mail, config | `application/`, `domain/` — to implement their ports |
| `presentation/` | driving adapters: HTTP API, CLI, workers | `application/` and `domain/` types; concrete infrastructure **only inside the composition root** |

> ⚠️ A layered import contract is often written as a single stack
> (`presentation → infrastructure → application → domain`). That is a
> **permission ordering** for a linter — "each layer may import those below it" —
> **not a call chain**. It does not mean a router should reach the application
> layer *through* infrastructure. A handler calls a use case directly; the only
> place it touches a concrete adapter is where dependencies are wired.

The domain must not reach FastAPI, SQLAlchemy, Pydantic, Starlette, HTTP status
codes, JSON, sessions, DI containers or loggers — **not even transitively**.

Four layers is a *choice* (it comes from Clean Architecture), not part of
hexagonal architecture, which describes two zones and ports. Keep the rule and
the slicing distinct.

## Before you change anything

Read the project first. Answer, in this order:

1. What business rules actually exist? Which are invariants, which are policies?
2. Where are the meaning boundaries (bounded contexts)? → `references/strategic-ddd.md`
3. What must stay consistent **within a single transaction**? That is an aggregate.
4. Which concepts have identity (entities) and which are defined by value (value objects)?
5. Which operations are use cases — one per business action?
6. Which capabilities must be expressed as ports, and in which layer?
7. Which current imports point outward?

Do not introduce an abstraction just because a reference architecture has one.
Prefer the simplest structure that represents the domain honestly.

## The central skill: where does a rule live?

"Business rules go in the domain" is far too coarse to decide with. Use this:

```
A rule to place
├─ Is it about the validity of a single value?          → value object (validate on construction)
├─ Is it about the internal state of one aggregate?     → method on the entity / aggregate root
├─ Is it business, but owned by no object?              → domain service (stateless, no I/O)
├─ Is it sequencing, coordination, or a policy of this
│  particular use case (quota, cap, pagination)?        → use case (application layer)
└─ Is it a technical guarantee?                         → infrastructure (FK, UNIQUE, index)
```

The decisive test when you hesitate:

> If this operation were triggered tomorrow by a CSV import, a cron or a broker
> message — must the rule still apply?
>
> - **Yes, always** → domain. It is constitutive of the object.
> - **Yes, but differently per entry point** → application (policy).
> - **No, it is specific to this channel** → adapter (HTTP schema, CLI argument).

Corollary, stated honestly: a use case holds no **domain invariants**, but it
may hold the **policy of that use case**.

### Guarantees usually live at three levels

Uniqueness, referential integrity and similar rules are not one decision:

| Level | What it provides |
|---|---|
| Use case checks the port first | the readable **message** |
| Constraint in the database | the actual **guarantee**, including under concurrency |
| Adapter translates the violation | makes the guarantee **audible** as a business error |

Checking in the application without a constraint is a race condition waiting to
happen. Adding the constraint without translating it produces an unreadable
technical error — and, depending on *when* your transaction commits, possibly no
error at all that the client can see. For state-changing HTTP methods, commit
**before** the response is built; a flush in the adapter translates violations
but is not a commit. See `transactions-and-errors.md`.

## Workflows

### Reviewing an existing project

1. Map the actual import graph; run or add an import checker.
2. List domain concepts and workflows in business vocabulary.
3. Find boundary violations: framework imports in the domain, ORM models leaking
   into the application, `HTTPException` outside `presentation/`, commits inside
   repositories, navigation between aggregates, anemic entities.
4. Separate architectural problems from style preferences.
5. Rank by impact: broken boundary → maintainability risk → unnecessary
   ceremony → optional polish.
6. Propose concrete, incremental changes with file paths. Prefer restoring a
   boundary over a rewrite.
7. Say plainly when part of the structure is **over-engineered** for the domain.

### Adding a feature

1. State the business rule independently of HTTP and persistence.
2. Place it with the decision tree above.
3. Add or amend the use case (one per business action).
4. Add only the ports the use case genuinely needs.
5. Implement the adapters.
6. Wire the presentation layer; keep handlers translation-only.
7. Test at the **lowest meaningful layer** — a domain rule needs no HTTP test.
8. Run lint, type checking, the import contracts and tests.

### Starting a project

1. First decide whether the domain complexity justifies this at all
   (see *When not to apply this*).
2. Write the ubiquitous language before any file: names and definitions.
3. Identify the initial bounded contexts.
4. Build **one thin vertical slice** end to end, core outward: domain →
   application → adapters → wiring.
5. Add the dependency check in CI **on day one**. Added six months later it
   never passes first try.
6. Add infrastructure only when a real need appears. Do not pre-build adapters.

## When not to apply this

The cost is real — more files, mappers, indirection — and it is repaid by a
**rich domain** over a **long life**. Signals it is oversized:

- CRUD whose only invariant is "this field is required": the entities will be
  DTOs with a mapper, pure ceremony.
- A throwaway prototype, a script, a one-off analysis.
- One person, three months, a need that will not outlive the quarter.
- A service whose real work is elsewhere — a proxy, an ETL, a file transformer.
  Their complexity is technical, not domain-shaped.

There is also a middle ground, and it does not have to be taken as a block.
By decreasing benefit/cost ratio:

1. Self-validating value objects — nearly free, immediate payoff.
2. Rules inside entities instead of routers — also free.
3. Use cases callable outside HTTP — the day a CLI or a cron appears.
4. Ports and mappers — the expensive one. Take it when substitutability or
   I/O-free testability becomes a genuine need.

Many projects gain enormously from 1 and 2 and never need 4. Say so.

## Principle vs. one project's choice

When advising, keep these apart. Transferable principles: the dependency rule,
value objects, aggregate boundaries, references by identity, ports owned by the
layer that expresses the need, transaction boundary around the unit of work,
business vs. technical errors, a single composition root.

Implementation choices that must **not** be presented as laws: the number of
layers, UUIDv7 identities, `dataclass(frozen=True, slots=True)`, RabbitMQ,
Valkey/Redis, PostgreSQL, testcontainers, a dependency-injection facade,
import-linter specifically. Recommend them when they fit; never impose them.

If a project does not need a cache, say it does not need a cache.

## Reference files

Load only what the task needs.

| File | Load it when |
|---|---|
| `references/architecture.md` | placing rules, layering, ports vs adapters, enforcing the dependency rule |
| `references/strategic-ddd.md` | finding bounded contexts, context maps, ACLs, running a discovery workshop |
| `references/domain.md` | value objects, entities, aggregates, invariants, relations, domain exceptions |
| `references/application.md` | use cases, port placement, DTOs, policies, avoiding ceremony |
| `references/persistence.md` | ORM models, mappers, repositories, SQLAlchemy pitfalls |
| `references/transactions-and-errors.md` | transaction boundaries, unit of work, error hierarchies, composition root |
| `references/reads-and-writes.md` | query services, N+1, CQRS, bulk imports, reconstitution, idempotence |
| `references/events-and-messaging.md` | caching, domain vs integration events, dual writes, outbox, when a broker is justified |
| `references/testing.md` | the three test levels, hand-written fakes, integration setup, review checklist |
| `references/project-structure.md` | directory layout, vertical slicing, the startup recipe |

### Canonical decisions

When references overlap, treat these files as authoritative and make the others
link back rather than restating a competing rule:

| Decision | Canonical reference |
|---|---|
| Port ownership and repository placement | `architecture.md` |
| Commit timing, `flush`, inbox/outbox and consumer idempotency | `transactions-and-errors.md` |
| Domain/integration event dispatch timing | `events-and-messaging.md` |
| Aggregate reconstitution and intrinsic invariants | `domain.md` |
| Repository vs. query-service read paths | `reads-and-writes.md` |

## Two questions that carry the whole skill

> **Whose decision is this?**
> **What must be consistent within a single transaction?**

Ports, mappers, DTOs and composition roots are only the machinery that makes the
answers executable. A choice that protects the core's isolation while keeping
the code readable is probably good, even if it matches no named pattern. A
design that follows every named pattern but that nobody can tie to a problem is
probably bad.
