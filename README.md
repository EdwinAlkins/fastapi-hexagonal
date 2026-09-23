# Task Manager — référence FastAPI, hexagonale, DDD & déploiement

[![Cours en ligne](https://img.shields.io/badge/Cours-15%20chapitres-1f6feb?style=flat-square)](https://edwinalkins.github.io/fastapi-hexagonal/cours/index.html)
[![Publication du site](https://img.shields.io/github/actions/workflow/status/EdwinAlkins/fastapi-hexagonal/pages.yml?branch=main&label=GitHub%20Pages&style=flat-square)](https://github.com/EdwinAlkins/fastapi-hexagonal/actions/workflows/pages.yml)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue?style=flat-square)](LICENSE)

[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](backend/src/task_manager/presentation/api)
[![SQLAlchemy 2 async](https://img.shields.io/badge/SQLAlchemy-2%20async-D71F00?style=flat-square)](backend/src/task_manager/infrastructure/persistence)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](docker-compose.yml)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?style=flat-square&logo=rabbitmq&logoColor=white)](backend/src/task_manager/presentation/worker)
[![Valkey](https://img.shields.io/badge/Valkey-cache-1A1A1A?style=flat-square&logo=redis&logoColor=white)](backend/src/task_manager/infrastructure)
[![Preact](https://img.shields.io/badge/Preact-673AB8?style=flat-square&logo=preact&logoColor=white)](frontend/)
[![Kubernetes (Kind)](https://img.shields.io/badge/Kubernetes-Kind-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](k8s/README.md)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%2C%20Codex%2C%20Cursor-8A63D2?style=flat-square)](plugins/fastapi-hexagonal-ddd/README.md)

**📖 Documentation : <https://edwinalkins.github.io/fastapi-hexagonal/>** — le
cours complet, la section infrastructure et la carte du dépôt, publiés depuis
[`docs/`](docs/).

---

Dépôt **full-stack** conçu pour servir de **référence** : une application réelle
(gestionnaire de tâches) illustrant une architecture **hexagonale (ports &
adapters)**, du **DDD tactique**, des pratiques de **Software Craftsmanship**,
et un déploiement **local (Docker Compose)** puis **Kubernetes (Kind)**.

Le métier est volontairement simple. L’intérêt n’est pas le produit, mais
**comment** le code, les tests, les contrats d’architecture et l’infra sont
organisés pour rester reproductibles sur un autre projet.

> Le cœur métier ne dépend d’aucun détail technique (BDD, framework web, JSON).
> Les détails se branchent *sur* le cœur, jamais l’inverse.

---

## Ce que ce dépôt enseigne

| Sujet | Où le voir |
|-------|------------|
| Règle de dépendance (hexagonale) | `backend/src/task_manager/` + [cours](backend/docs/cours/01-regle-de-dependance.md) |
| DDD tactique (VO, entités, agrégats, 1→n) | contextes `task` / `user` + [cours](backend/docs/cours/03-le-domaine.md) |
| Où placer une règle (le chapitre central) | [cours](backend/docs/cours/02-ou-vit-une-regle.md) |
| Use cases, ports, DTO neutres | `application/` + [cours](backend/docs/cours/06-application-et-ports.md) |
| Adaptateurs (ORM, HTTP, worker, CLI) | `infrastructure/`, `presentation/` |
| Craftsmanship (lint, types, imports, tests, hooks) | `backend/Makefile`, `pyproject.toml`, `.pre-commit-config.yaml` |
| Stack locale reproductible | `docker-compose.yml` |
| Déploiement K8s (Kind, CNPG, opérateurs, HPA, NetworkPolicy) | [`k8s/`](k8s/README.md) |

Le **cours progressif** (15 chapitres) vit dans
[`backend/docs/cours/`](backend/docs/cours/README.md). C’est le fil à suivre
si l’objectif est de **reproduire** l’exercice ailleurs.

---

## Vue d’ensemble

```
┌─────────────┐     HTTP      ┌──────────────┐     ports      ┌─────────────┐
│  Frontend   │ ───────────► │  API FastAPI │ ─────────────► │  Use cases  │
│  Preact SPA │  /api/v1     │  Gunicorn    │                │  + domaine  │
└─────────────┘              └──────┬───────┘                └──────┬──────┘
                                    │                               │
                     ┌──────────────┼──────────────┐                │
                     ▼              ▼              ▼                ▼
                PgBouncer       Valkey         RabbitMQ          Worker
                     │          (cache)       (événements)     (e-mails)
                     ▼
                 PostgreSQL
```

Deux **bounded contexts** : `user` et `task`, liés par une relation **1→n**
(`Task` référence `User` par identité, pas par objet). Le partage d’une tâche
publie un événement RabbitMQ ; un **worker** envoie l’e-mail (Mailpit en local).

---

## Structure du dépôt

```
.
├── backend/                 # API, worker, CLI — architecture hexagonale
│   ├── src/task_manager/
│   │   ├── domain/          # cœur pur (entités, VO, ports, exceptions)
│   │   ├── application/     # use cases + ports transverses (cache, smtp, bus)
│   │   ├── infrastructure/  # adaptateurs driven (SQLAlchemy, Valkey, RabbitMQ…)
│   │   ├── presentation/    # adaptateurs driving (API, worker, CLI)
│   │   └── main.py
│   ├── tests/               # unitaires (purs) + intégration (testcontainers)
│   ├── alembic/             # migrations (schéma versionné)
│   ├── docs/cours/          # cours d’architecture
│   └── README.md            # prise en main backend
├── frontend/                # SPA Preact (Vite, TanStack Query, Tailwind)
├── plugins/                 # Agent Skill installable (Claude Code / Codex / Cursor)
│   └── fastapi-hexagonal-ddd/
├── docker-compose.yml       # stack locale complète
├── .env.template            # secrets / ports (copier en .env)
└── k8s/                     # Kind + CloudNativePG + Gateway API + durcissement
```

### Couches backend (tout pointe vers l’intérieur)

```
presentation  →  infrastructure  →  application  →  domain
     (HTTP, worker, CLI)              (use cases)      (sans framework)
```

Chaque couche est **tranchée par contexte** (`domain/task/`, `domain/user/`, …).
La règle de dépendance n’est pas un vœu pieux : **import-linter** la vérifie
sur le graphe d’imports réel (`make imports` depuis `backend/`).

Détail des conventions : [`backend/README.md`](backend/README.md) et
[`backend/CLAUDE.md`](backend/CLAUDE.md).

---

## Stack

| Couche | Choix |
|--------|--------|
| API | FastAPI, Gunicorn + Uvicorn workers, Pydantic v2 |
| Langage | Python **3.14**, [uv](https://docs.astral.sh/uv/) |
| Persistance | SQLAlchemy 2 async, asyncpg, PostgreSQL 17, **PgBouncer** (mode transaction) |
| Schéma | Alembic (`migrate` avant `api` / `worker`) |
| Cache | Valkey (protocole Redis) |
| Messagerie | RabbitMQ + worker dédié (même image que l’API) |
| Mail (dev) | Mailpit |
| Observabilité | Prometheus (`/metrics`) |
| Front | Preact (`preact/compat`), TypeScript, Vite 8, TanStack Query, Tailwind 4 |
| Qualité | ruff, mypy strict, import-linter, pytest, testcontainers, pre-commit |

---

## Démarrage rapide (stack complète)

Prérequis : Docker (Compose).

```bash
cp .env.template .env          # adapter les secrets
docker compose up --build
```

| Service | URL |
|---------|-----|
| Application (front) | http://localhost:5173 |
| API + OpenAPI | http://localhost:8000/docs |
| Health / ready | http://localhost:8000/health · `/ready` |
| Mailpit | http://localhost:8025 |
| RabbitMQ management | http://localhost:15672 |
| RedisInsight | http://localhost:5540 |
| Prometheus | http://localhost:9090 |

Les migrations Alembic tournent dans le service one-shot `migrate`, **en
connexion directe Postgres** (pas via PgBouncer : Alembic a besoin d’une session
stable — son verrou consultatif est *de session*, et certaines opérations comme
`CREATE INDEX CONCURRENTLY` ne peuvent pas vivre dans une transaction). L’API et
le worker passent ensuite par le pooler.

### Backend seul (hot-reload)

```bash
docker compose up -d postgres pgbouncer valkey rabbitmq mailpit
cp .env.template .env
cd backend
uv sync
uv run alembic upgrade head
make run          # → http://localhost:8000/docs
make worker       # consumer RabbitMQ (autre terminal)
```

### Frontend seul (hôte)

L’API doit déjà tourner (`docker compose up -d api` ou `make run`).

```bash
cd frontend
npm install
npm run dev       # → http://localhost:5173  (proxy Vite → localhost:8000)
```

---

## Craftsmanship (filets de sécurité)

L’architecture se **défend** dans la CI locale, pas seulement dans les docs.

Depuis `backend/` :

| Commande | Rôle |
|----------|------|
| `make lint` | ruff + import-linter + mypy strict |
| `make test` | unitaires + intégration |
| `make test-unit` | domaine / use cases, sans I/O |
| `make test-integration` | API de bout en bout (Docker / testcontainers) |
| `make check` | lint + tests (équivalent CI locale) |
| `make precommit-install` | hooks git (ruff, mypy, contrats d’imports) |

Principes visibles dans le code :

- **Domaine pur** : pas de FastAPI / SQLAlchemy / Pydantic dans `domain/`.
- **Un use case = une action** ; DTO dataclasses, pas de schémas HTTP.
- **Identités UUIDv7** générées par le domaine.
- **Agrégats liés par ID** ; les contrôles cross-agrégat vivent dans l’application.
- **Transaction = requête HTTP** (les repositories ne commitent pas).
- **Exceptions métier** → codes HTTP via des bases sémantiques (`NotFound` → 404, etc.).
- **Composition root** : le câblage ports → adaptateurs est isolé dans
  `presentation/api/dependencies/`.

Recette pour **démarrer un autre projet** :
[chapitre 13](backend/docs/cours/13-demarrer-un-projet.md) (y compris *quand ne
pas* utiliser cette architecture).

---

## API (aperçu)

Une tâche appartient toujours à un utilisateur. Création et liste : routes
imbriquées sous le propriétaire. Mutations d’une tâche : `/api/v1/tasks/{id}`.

| Méthode | Route | Description |
|---------|-------|-------------|
| POST / GET / PATCH | `/api/v1/users` … | Utilisateurs (GET by id caché) |
| POST / GET | `/api/v1/users/{id}/tasks` | Créer / lister les tâches d’un user |
| GET / PATCH / DELETE | `/api/v1/tasks/{id}` | Lire, renommer, supprimer |
| POST | `/api/v1/tasks/{id}/start` · `/complete` · `/share` | Cycle de vie + partage |

Exemple :

```bash
USER=$(curl -s -X POST localhost:8000/api/v1/users \
  -H 'content-type: application/json' \
  -d '{"name": "Ada Lovelace", "email": "ada@example.com"}' | jq -r .id)

curl -X POST localhost:8000/api/v1/users/$USER/tasks \
  -H 'content-type: application/json' \
  -d '{"title": "Rédiger le rapport"}'
```

Liste complète : [`backend/README.md`](backend/README.md#api).

---

## Déploiement

Deux niveaux, **même règles applicatives** (Alembic, PgBouncer en transaction,
`prepared_statement_cache_size=0`, worker = même image que l’API).

### 1. Docker Compose (dev / démo)

`docker-compose.yml` : postgres, pgbouncer, valkey, rabbitmq, mailpit,
prometheus, migrate, api, worker, frontend.

Variables : `.env.template` (préfixe `APP_` côté application).

### 2. Kubernetes local (Kind)

Manifestes dans [`k8s/`](k8s/) : cluster Kind, **Gateway API** (Envoy Gateway), **CloudNativePG**
(Postgres + Pooler), opérateur RabbitMQ, Job de migration, HPA, PDB,
NetworkPolicies, SecurityContext.

```bash
./k8s/deploy.sh
```

Application : **http://localhost**. Consoles : `mailpit.localhost`,
`rabbitmq.localhost`, `redisinsight.localhost`, `prometheus.localhost`.

Guide pas à pas, durcissement et backups : [`k8s/README.md`](k8s/README.md).
Correspondance compose → K8s :
[section infrastructure](https://edwinalkins.github.io/fastapi-hexagonal/infra/index.html).

Ce n’est **pas** un runbook de production cloud (pas de TLS managé, pas de
secret store distant). C’est une **cible pédagogique** proche d’une prod
sérieuse : opérateurs, pooling, migrations one-shot, isolation réseau,
autoscaling.

---

## Agent Skill installable

Le savoir de ce dépôt est distribué comme **Agent Skill** — utilisable par Claude
Code, OpenAI Codex et Cursor sur *n'importe quel* projet, pas seulement celui-ci.
Il transmet la méthode (règle de dépendance, placement des règles, frontières
d'agrégats, ports, query services, transactions) plutôt que le code.

**Claude Code**

```
/plugin marketplace add EdwinAlkins/fastapi-hexagonal
/plugin install fastapi-hexagonal-ddd@fastapi-hexagonal
```

**OpenAI Codex**

```bash
codex plugin marketplace add EdwinAlkins/fastapi-hexagonal
codex plugin add fastapi-hexagonal-ddd@fastapi-hexagonal
```

**Cursor**

```
/add-plugin https://github.com/EdwinAlkins/fastapi-hexagonal
```

Puis installer `fastapi-hexagonal-ddd` depuis Customize.

Détails et contenu : [`plugins/fastapi-hexagonal-ddd/`](plugins/fastapi-hexagonal-ddd/README.md).

---

## Parcours de lecture recommandé

1. Ce README (carte du dépôt).
2. [Cours](backend/docs/cours/README.md) — chapitres 00 → 14.
3. Code du contexte `user` (tranche verticale minimale) puis `task` (1→n + worker).
4. [`backend/README.md`](backend/README.md) pour ajouter un use case.
5. [`k8s/README.md`](k8s/README.md) pour le déploiement.
6. [`plugins/fastapi-hexagonal-ddd/`](plugins/fastapi-hexagonal-ddd/README.md) pour réutiliser la méthode ailleurs.

Articles / notes annexes (historique du POC) : dossier [`resources/`](resources/).

---

## Prérequis par usage

| Objectif | Prérequis |
|----------|-----------|
| Jouer avec l’app | Docker |
| Développer le backend | Python 3.14, uv, Docker (tests d’intégration) |
| Développer le front | Node / npm, API déjà up |
| Déployer sur Kind | docker, kind, kubectl ; ports 80/443 libres |

---

## Licence

Ce dépôt est sous licence **[GNU AGPL v3](LICENSE)** (copyright William Nauroy, 2026).

Le code peut être étudié, modifié et redistribué, y compris commercialement,
mais toute version modifiée — distribuée **ou exposée à des utilisateurs via un
réseau** (SaaS, API) — doit être publiée sous la même licence, avec son code
source rendu accessible à ces utilisateurs.

Ce n’est pas un produit à déployer tel quel : secrets, durcissement et
observabilité restent à adapter avant un usage réel.
