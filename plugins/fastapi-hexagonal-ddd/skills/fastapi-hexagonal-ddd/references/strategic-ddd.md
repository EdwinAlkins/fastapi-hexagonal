# Strategic DDD: boundaries before patterns

> Getting a pattern wrong costs a class rewrite. Getting a **boundary** wrong
> costs a system rewrite.

Impeccable tactical modelling on bad boundaries produces a system that is clean
locally and incoherent globally — the worst case, because it looks good. Order
matters: **strategic first, tactical second.**

This is also the half that cannot be learned from a repository. A boundary is
not visible in a file; it is visible in what *several people* understand when
they say the same word. Code shows the result of a split, never the reasoning,
nor the three splits that were rejected.

## What strategic DDD actually decides

Three things, and nothing else:

| Decision | Question it answers | Deliverable |
|---|---|---|
| **Ubiquitous language** | Which word for which thing, and who uses it? | A glossary per context |
| **Bounded contexts** | Where do the boundaries of meaning fall? | A list of named contexts |
| **Context map** | How do contexts talk, and who is subject to whom? | A relationship diagram |

These are contracts, not documentation: the glossary says what the code is
allowed to name, the contexts say what may depend on what, the map says who
breaks whom when something changes.

## Bounded context, usefully defined

A **bounded context** is a boundary within which a **model and its language are
coherent**, and whose rules of meaning are under control.

The easiest observable signal: **if two people use the same word for two
different things, examine a separation.** Not "they should agree" — they are
both right, in their context.

Caveat that matters: vocabulary is a strong signal, not proof. Two teams can
share a word and its definition and still need separate models, because of
lifecycle, rate of change, or ownership. The boundary is decided on the
**model**, not on the lexicon alone.

The reflex to unlearn: looking for the single model that satisfies everyone. It
does not exist, and chasing it always produces the same thing — a class that
grows, full of optional fields meaningful to half the callers, that nobody dares
change.

> **Duplicating a concept across two contexts is not duplication to be
> eliminated.** This is where nearly everyone goes wrong, because ten years of
> training to factor out says the opposite.

Canonical example: in e-commerce, `Product` in `catalog` is a description with
photos, categories and a display price; in `ordering` it is a reference, a price
frozen at order time and a quantity. Same word, two concepts. The right answer
is not a universal `Product` — it is recognising there are two.

## Symptoms of wrong boundaries

Check you have a problem before running a workshop.

| Symptom | What it reveals | How to spot it |
|---|---|---|
| A central class everyone imports (`User`, `Order`, `Product`) | Several contexts fused by force | `grep -rc "import User"` — everywhere is the signal |
| Optional fields in clusters ("these 6 are only for billing") | Two concepts in one class | Read the `\| None`s and see if they group |
| One word defined differently per speaker | An unnamed boundary of meaning | Sit in two business meetings |
| Commits that always touch 5 modules | Boundary in the wrong place | `git log --name-only` over 3 months |
| A "service" or "manager" that grows forever | The missing context, unnamed | Classes over ~300 lines |
| Tables permanently joined in queries | Real cohesion not reflected | Read the recurring `JOIN`s |

No symptoms at all? You probably have no strategic problem. Say so instead of
inventing one.

## The procedure

Roughly one day for a mid-sized system, or two half-days a week apart (better —
people think in between).

### Step 0 — Get the right people in the room

The step most often botched, and it decides everything else.

**Present:** 1–3 **domain experts** — the people who *do* the work, not those who
manage it (the salesperson who enters orders beats the sales director); 2–5
**developers**, including whoever will maintain the code; 1 **facilitator** who
takes no side on the model, whose only job is to make experts talk and stop
developers from talking technical.

**Absent:** anyone with an interest in defending the existing architecture —
including you, if you wrote it.

**Material:** a wall, sticky notes in 4 colours, markers. No screen, no digital
whiteboard while a physical wall is possible: the physical constraint forces
synthesis, an infinite canvas dissolves it.

**Golden rule:** developers listen and write; they do not propose models. The
moment someone says "we could have a table…", the facilitator cuts in.

### Step 1 — EventStorming, big picture (2–3 h)

1. **Events** (orange notes). Everyone writes everything that *happens*, in the
   **past tense**: "Order placed", "Payment accepted", "Parcel shipped". Twenty
   minutes of silent writing, no discussion.
2. **Timeline.** Order the notes left to right. Duplicates appear, so do gaps.
   It is noisy; that is normal.
3. **Hot spots** (red notes). Every disagreement or open question gets a red note
   and you **move on**. Never resolve a disagreement on the spot — recording it
   is worth more than settling it.
4. **Actors and external systems.** Who triggers what, who receives what.

Deliverable: a photographed wall of ordered events, plus the list of red notes —
which is often worth more than the rest.

### Step 2 — Find the ruptures

Three things to look for on the wall:

- **Vocabulary ruptures.** The point where "customer" stops meaning *prospect to
  convince* and starts meaning *delivery address*.
- **Temporal pivots.** Where the process waits: human validation, external
  payment, delivery. A wait is almost always a boundary — immediate consistency
  is already impossible there.
- **Actor changes.** When the acting person changes, the vocabulary almost
  always changes with them.

The decisive exercise: take each important noun and ask out loud *"does this mean
the same thing here and there?"*. **Every "well, not quite" is a boundary.**

### Step 3 — Name candidate contexts

Circle zones of the wall and give them **business** names (`Billing`,
`Shipping`, `Catalog`) — never technical ones (`Core`, `Common`, `Shared`).

Then write each one's **glossary**: 5–15 terms with their definition *in this
context*. The glossary is the deliverable that survives best; two years later it
is often the only artefact still read.

A context without a written glossary is not a context, it is a folder.

### Step 4 — Draw the context map

For each pair of contexts that talk:

| Relationship | Meaning | When to choose it | Cost |
|---|---|---|---|
| **Shared kernel** | A small common core, changed by mutual agreement | Very close teams, genuinely stable core | High over time: every change is negotiated |
| **Customer / supplier** | Upstream commits to serve downstream; downstream can negotiate | Two teams, an accepted dependency | Medium: needs a real relationship |
| **Conformist** | Downstream adopts the upstream model as-is | Upstream will never move (legacy, third-party API) | Low now, poisonous later |
| **Anti-corruption layer** | Downstream translates the upstream model into its own | Upstream model is unfit or unstable | Most expensive to write, cheapest to live with |

Add one arrow per relationship and **write the direction of the dependency** —
who breaks whom when something changes. That is the most useful information on
the whole diagram.

The **ACL** is the one to know by heart. It is the same idea this architecture
applies everywhere at small scale: a mapper protects the domain from the ORM; an
ACL protects a context from another system's model. Whenever you integrate
something you do not control — a CRM, a payment API, a client's legacy system —
the question is not *whether* you write an ACL but when you will regret not
having one.

### Step 5 — Decide what to build, and in what order

Not every identified context deserves to exist in code **today**:

- **Core domain** — what creates differentiated value in this business. Focus
  tactical effort there: aggregates, invariants, thorough tests. Many products
  have one dominant core; several cores are possible when the business truly has
  several independent sources of advantage.
- **Supporting** — necessary but not differentiating. An honest CRUD may be enough.
- **Generic** — capabilities available as commodities. Prefer buying when the
  capability is not differentiating; auth, billing or notifications can still be
  core in businesses whose advantage is precisely there.

The classic mistake is applying the full treatment to all three. The real
strategic move is deciding **where you do not invest**.

## Five tests before accepting a boundary

Any one of these can disqualify a split.

1. **The word test** — does each term have exactly one meaning inside this
   context? Two meanings and the boundary is probably misplaced. Strong signal,
   not proof: the model decides, not the lexicon.
2. **The transaction test** — is everything that must be consistent
   *immediately* inside? A cross-context synchronous invariant is strong evidence
   that the boundary is misplaced, but shared infrastructure or an explicit
   coordination protocol may be a deliberate exception. Treat this as a design
   pressure, not a theorem.
3. **The team test** — can one team own this context end to end? A context that
   needs three teams to move is not autonomous. (Corollary of Conway's law: your
   split will end up resembling your org chart whether you like it or not — so
   choose it.)
4. **The deployment test** — could it, in theory, be deployed alone? You need not
   actually do it. But if the answer is "impossible", the boundary is fictional.
5. **The glossary test** — can you write 10 terms defined without ever referring
   to another context? If every definition says "see context X", there is one
   context.

## What boundaries change in code — and what they do not

**Changes:**

- One root package per context, with its own complete vertical slice.
- **No direct imports** between contexts, except identities.
- An explicit contract at each boundary: a shared identity, an integration
  event, or an ACL.
- One import-linter contract per boundary, so it stays true.

**Does not necessarily change:**

- **The number of databases.** A context can live in a logical schema of the same
  database. Physical separation is a deployment decision, not a modelling one.
- **The number of deployed services.** A modular monolith with four contexts is
  often better than four microservices — and infinitely easier to fix when a
  boundary turns out to be wrong.
- **The existence of a minimal shared kernel.** A few logic-free classes
  (exception base types, technical types) are acceptable. The moment a **rule**
  enters it, split it.

> **The healthy sequence:** split into modules inside a monolith first. Live with
> it for six months. Then extract what has proven its autonomy. The reverse —
> extracting before living with it — is the most reliable way to freeze a bad
> boundary into network calls.

## Honesty about labels

"Two modules in one bounded context" is very often the accurate description of
what people call "two bounded contexts". Two well-separated aggregates,
referenced by identity, with no cross-imports, is exactly the right thing to do —
the work is sound; only the label oversells.

It still matters, because a project that presents itself as a reference teaches
"bounded context = one subfolder per entity" to whoever copies it. When
reviewing, prefer the exact word:

> These slices are **modules** (or aggregates), not bounded contexts: the term
> has a single meaning across the whole system. The vertical split prepares a
> future extraction; it does not claim a boundary of meaning.

"Bounded context" sounds better than "module". That is precisely why it needs
watching: the most prestigious word is rarely the most exact.

## Going further

- **Domain-Driven Design** (Eric Evans) — parts **IV and V**, the two thirds
  almost nobody reads. The strategic material is there.
- **Domain-Driven Design Distilled** (Vaughn Vernon) — 150 pages straight to the
  strategic; best time/value ratio in the field.
- **Introducing EventStorming** (Alberto Brandolini) — step 1, by its author.
- **Team Topologies** (Skelton & Pais) — software boundaries and team
  boundaries; the modern companion to Evans' context chapters.
