# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

SPA front-end of the Task Manager POC, consuming the FastAPI backend in `../backend` (which has its own `CLAUDE.md` covering the hexagonal/DDD server side). Two screens: pick/create a user (`/`), then manage that user's tasks (`/users/:userId/tasks`).

All UI copy and code comments are in **French** — match this when adding code.

Stack: **Preact** (via `preact/compat`, so the code reads as React) · TypeScript · Vite 8 · TanStack Query v5 · react-router-dom v6 · Tailwind v4 · Headless UI.

Infra lives one level up: `../docker-compose.yml` (frontend, api, pgbouncer, postgres, valkey, rabbitmq, mailpit, redisinsight) + `../.env.template`.

## Commands

```bash
npm install
npm run dev        # Vite dev server → http://localhost:5173 (proxies /api → localhost:8000)
npm run build      # tsc -b && vite build → dist/
npm run preview    # serve the built dist/

docker compose up frontend    # from ../ : dev container with hot-reload, proxies /api → http://api:8000
```

**There is no test runner, linter, or formatter in this project** — don't go looking for one or invent a `npm test`. `npm run build` (which runs `tsc -b` first) is the only automated check, so run it after non-trivial changes. TypeScript is strict-ish via `tsconfig.app.json` (`noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`, `verbatimModuleSyntax` — type-only imports must use `import type`).

The dev server needs the API for anything to load: `docker compose up -d api` from `../` is the minimum.

## It's Preact, not React

Imports say `react` / `react-dom` / `@headlessui/react`, but nothing pulls in React at runtime:

- `@preact/preset-vite` aliases `react`/`react-dom` → `preact/compat` at build time (its `reactAliasesEnabled` default);
- `tsconfig.app.json` mirrors that with `paths` + `jsxImportSource: "preact"` so the types line up.

So: keep importing from `react` (that's the established convention here), but **never add a real React dependency** — `react` is not in `package.json`, only `@types/react` is. Anything depending on React internals (Suspense-heavy libs, react-dom/server, devtools-coupled packages) may not work under compat. Note DOM event handlers get Preact's typing: read values off `e.currentTarget.value` (see `Input`/`HomePage`), not `e.target.value`.

## API wiring — three environments, one relative path

`VITE_API_BASE_URL` is **empty by default**, so `api/client.ts` issues same-origin requests to `/api/v1/...` and something else routes them. That indirection is deliberate: the browser can't resolve the Docker hostname `api`, so nothing in the browser bundle may ever hardcode it.

| Where | What routes `/api` |
|-------|--------------------|
| `npm run dev` on the host | Vite proxy → `http://localhost:8000` (`vite.config.ts`) |
| `docker compose up frontend` | Vite proxy → `VITE_API_PROXY_TARGET=http://api:8000` |
| Production image | Nginx `location /api/` → `http://api:8000/api/` (`nginx.conf`) |

`VITE_API_BASE_URL` only exists as a build arg escape hatch for deployments where the API sits on another origin. Vite inlines `VITE_*` vars at **build** time — in the production image they're `ARG`s in `Dockerfile`, not runtime env, so changing one means rebuilding.

## Architecture

Layered top-down, each layer only knowing the one below:

- **`api/`** — the only place that talks HTTP. `types.ts` mirrors the backend's OpenAPI contract by hand (snake_case fields kept as-is: `owner_id`, `created_at`); `client.ts` exposes a flat `api` object of one method per endpoint. Regenerable from `/openapi.json` later, so keep it mechanical — no business logic here.
- **`hooks/`** — TanStack Query wrappers (`useTasks`, `useUsers`). **Components never call `api` directly**; they go through a hook.
- **`pages/`** — route-level screens, own the local UI state (forms, filters, pagination).
- **`components/`** — `ui/` holds generic primitives (`Button`, `Card`, `Input`, `Modal`); the level above holds domain-aware cards (`TaskCard`, `UserCard`).
- **`contexts/CurrentUser.tsx`** — in-memory only, no persistence: a page reload drops the selection, and `DashboardPage` rehydrates it from `useUser(userId)` in an effect. The URL, not the context, is the source of truth for *which* user is displayed.

### Key conventions

- **Tasks are reached through their owner.** `POST/GET /api/v1/users/:userId/tasks` for create/list, but `/api/v1/tasks/:taskId` for rename/start/complete/delete. This mirrors the backend's aggregate design (`Task` holds an `owner_id`; "a user's tasks" is a query, not aggregate navigation) — keep new task endpoints on the same split.
- **Query keys are built by exported helpers**, never inlined: `usersQueryKey` (constant) and `tasksQueryKey(userId)` (function), both extended with `{ limit, offset }` for the actual list query. Every mutation invalidates the **base** key (`tasksQueryKey(userId)`), which prefix-matches all paginated variants at once. A new mutation must do the same, or a page will show stale data.
- **Errors surface as `ApiError`.** `request()` unwraps FastAPI's `{"detail": "..."}` into `ApiError.message` and keeps `status`/`body`; 204 resolves to `undefined`. Components render `err instanceof Error ? err.message : '<French fallback>'`. Mutations use `mutateAsync` in a `try/catch` that sets local `formError` state — there's no global error toast.
- **Tailwind v4 is configured in CSS, not JS.** There is no `tailwind.config.js`: the `@theme` block in `src/index.css` defines the tokens. Use the semantic ones — `ink`, `muted`, `surface`, `panel`, `line`, `accent`, `accent-soft`, `danger`, and the status trio `todo`/`progress`/`done` — instead of raw palette colors, and `font-display` (Fraunces) for headings. New status colors belong in `@theme` first.
- **Variants are lookup records, not conditional strings** (`variants`/`sizes` in `Button`, `statusStyles`/`statusLabels` in `TaskCard`). Tailwind's scanner only sees literal class strings, so keep them whole — never build a class by concatenating fragments.
- **Confirm destructive/irreversible actions**: start/complete use an inline confirm swap inside `TaskCard`; delete uses the Headless UI `Modal`.

### Known rough edges of the POC

Both live in `DashboardPage` — don't mistake them for bugs to "fix" incidentally:

- **The status filter is client-side over the current page only.** `useTasks` fetches one `PAGE_SIZE` page, then `filteredTasks` filters it in memory, so "Terminées" shows only the done tasks *of that page*. Real filtering needs a backend query param.
- **Pagination guesses.** `hasNext` is `data.length >= PAGE_SIZE` — no total count in the API — so the last full page still offers "Suivant", landing on an empty one.

## Configuration

Only `VITE_*` vars reach the browser; declare any new one in `src/vite-env.d.ts` (`ImportMetaEnv`) or it won't be typed. Current ones, all optional with in-code defaults: `VITE_API_BASE_URL` (see above), `VITE_MAIL_UI_URL` (Mailpit, `:8025`), `VITE_REDIS_INSIGHT_URL` (RedisInsight, `:5540`) — the last two only feed the header shortcut buttons in `Layout.tsx`.
