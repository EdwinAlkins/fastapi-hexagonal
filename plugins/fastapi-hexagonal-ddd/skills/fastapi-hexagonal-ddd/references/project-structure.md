# Project structure and how to start

## Two dimensions, not one

Most "by layer or by feature?" debates are badly posed: these are not competing
options, they are two **axes** of the same plane.

|  | `task` | `user` | cross-cutting |
|---|---|---|---|
| **presentation** | `v1/routers/tasks.py` | `v1/routers/users.py` | `app.py`, `error_handlers.py`, `dependencies/session.py` |
| **infrastructure** | `persistence/task/` | `persistence/user/` | `persistence/database.py`, `config.py`, `cache/`, `mail/` |
| **application** | `application/task/` | `application/user/` | `application/shared/` (technical ports, errors) |
| **domain** | `domain/task/` | `domain/user/` | `domain/shared/` (exception bases) |

**Layers** answer "what kind of responsibility?". **Contexts** answer "which
piece of the business?". The real question is: *which way do you split the
folders first?*

Splitting **by layer first, by context second** makes sense when the dependency
rule is verified between layers — the layers must then be obvious physical
boundaries. At a larger scale, if the contexts become separate services, you
would probably invert it.

## The vertical slice, concretely

```
domain/task/          domain/user/
application/task/     application/user/
persistence/task/     persistence/user/
v1/schemas/task.py    v1/schemas/user.py
v1/routers/tasks.py   v1/routers/users.py
dependencies/task.py  dependencies/user.py
```

The benefit: you work **by feature**. Adding a context means adding folders
without touching existing files, and you read a context end to end instead of
navigating ten catch-all modules.

The cost, worth knowing: some structural duplication between contexts (each has
its own mapper, repository, schemas) and the temptation to share too early. The
right answer to "these two contexts look alike" is usually **nothing at all** —
two contexts that evolve separately are allowed to look alike today and diverge
tomorrow. True cross-cutting code (`domain/shared/`, `application/shared/`, the
database engine) is what belongs to **no** business area.

## The right amount of centralisation

Do not split everything mechanically.

- The composition root may keep an `__init__.py` **façade** that re-exports
  everything, because its purpose *is* to be a single entry point.
- Transport schemas are simply split, **without** a façade: they are per-context
  contracts with no centralising role.

Splitting serves readability; it is not a dogma. A façade added "for symmetry" is
free coupling.

### The façade trade-off, stated honestly

|  | With a façade | Without |
|---|---|---|
| Import in a router | one line, one origin | one import per dependency module |
| Adding a use case | a provider **and** an `__all__` entry | a provider, that is all |
| Working as a team | everyone edits the same file → Git conflicts | each touches their own context |
| Import cost | loading the façade loads *all* providers | you load only what you use |

Two clarifications, because the usual criticism misses:

- **The façade does not couple the contexts to each other.** `dependencies/task.py`
  does not import `dependencies/user.py`: the aggregator depends on the parts,
  never the reverse. Dependency direction is what distinguishes a façade from
  coupling.
- **The verbose `__all__` is not ceremony.** Under strict type checking with no
  implicit re-export, names imported in an `__init__.py` are not re-exported
  without an explicit list. The boilerplate comes from the type checker, not from
  the pattern.

The tipping point: **the façade pays while one person touches that file.** With a
team, or past a few dozen providers, maintaining `__all__` costs more than it
returns, and per-context dependency modules imported directly by each router
become the better choice.

## Starting recipe, layer by layer

Starting from the core is counter-intuitive — you usually want to start from the
database or the API. That is precisely what keeps the domain pure: everything
written before a database exists is, by construction, independent of it.

### Step 0 — Language before code

Write the list of **business nouns** and their definitions. What *is* a task?
What exactly does "complete" mean? Who is allowed to do it? If you cannot
answer, no architecture will save you.

This is also where you look for **bounded contexts**. The most visible clue is
vocabulary: a "user" in the authentication sense (credentials, sessions, roles)
is not the same concept as a "user" in the business sense (owner of tasks), even
if they share an identifier. One word covering two concepts is a strong signal —
but it is the coherence of the *model* that decides, not the lexicon alone. See
`strategic-ddd.md`.

### Step 1 — The domain (no technical dependency)

1. Identify the **value objects**: concepts defined by their value, with their
   validity rules. Self-validating at construction.
2. Identify the **entities** and **aggregates** — above all the **transactional
   consistency boundaries**. Express invariants as methods (`order.confirm()`,
   not `order.status = ...`).
3. Write the **business exceptions**, organised by semantics (not found,
   conflict, validation).
4. Declare the **persistence ports** the model needs.

✅ Check: does the domain import with no framework? Do its unit tests run in
milliseconds? Write them **now**, not later.

### Step 2 — The application (depends on the domain only)

5. One **use case** per action. It receives ports, orchestrates, holds no
   invariants.
6. Neutral **DTOs** in (commands) and out.
7. The **technical ports** the use cases need (cache, notification, publication)
   — in `application/`, not in the domain.

### Step 3 — The adapters

8. **Persistence**: ORM models (distinct from entities), **mappers**, and the
   concrete port implementations. Repositories do not commit and receive their
   session.
9. **Entry points**: transport schemas, routers/commands/consumers that translate
   and nothing else.

### Step 4 — Cross-cutting wiring

10. The **transaction boundary**, provided by each driving adapter.
11. The translation of business / technical errors into the protocol.
12. The **composition root** binding ports to adapters.
13. End-to-end **integration tests** against real engines.

### Step 5 — Guard rails, immediately

14. The **automated dependency check** in CI from day one. Added after six
    months, it never passes first try.

## Starting skeleton

```bash
mkdir -p src/myproject/domain/{shared,my_context}
mkdir -p src/myproject/application/{shared,my_context}
mkdir -p src/myproject/infrastructure/persistence/my_context
mkdir -p src/myproject/presentation/api/v1/{routers,schemas}
mkdir -p tests/{unit/domain,unit/application,integration}
```

Build **one thin vertical slice** through all of it before widening. A single
context wired end to end — domain, application, persistence, DI, schemas,
routers, tests at all three levels — teaches more and costs less than four
half-built ones.

## Going further

- **Domain-Driven Design** (Eric Evans) — the founding book. The strategic part
  matters more than the tactical patterns, and is far less read.
- **Implementing Domain-Driven Design** (Vaughn Vernon) — more practical; the
  source of "reference aggregates by identity".
- **Hexagonal Architecture** (Alistair Cockburn, 2005) — the original ports &
  adapters article, short and still relevant.
- **Clean Architecture** (Robert C. Martin) — the dependency rule formalised, and
  the origin of the four-layer split used here.
- **Patterns of Enterprise Application Architecture** (Martin Fowler) — the
  reference definitions of *Repository*, *Unit of Work*, *Data Mapper*.
- **Architecture Patterns with Python** (Percival & Gregory) — the closest to this
  material: Python, ports & adapters, Unit of Work, events. Readable online.
