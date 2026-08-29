# FastAPI Clean — Template Architecture Hexagonale & DDD

Template FastAPI **prêt à cloner** illustrant une architecture **hexagonale
(ports & adapters)**, du **DDD tactique** et du **Software Craftsmanship**.
Domaine d'exemple : une gestion de tâches, avec deux contextes (`task`, `user`)
liés par une relation **1→n**.

**Stack :** FastAPI · SQLAlchemy 2 async · PostgreSQL (asyncpg, derrière
PgBouncer) · Valkey/Redis (cache) · RabbitMQ (worker de notifications) · Pydantic
v2 · pytest · ruff · mypy · import-linter · uv.

> 📚 **Envie de comprendre le _pourquoi_ ?** Un cours complet et progressif vit
> dans [`docs/`](docs/cours/README.md) (architecture, DDD, relations, transactions,
> tests…). Ce README ne couvre que la prise en main.

---

## Démarrage

Prérequis : [uv](https://docs.astral.sh/uv/), Python 3.14 et Docker (l'API a
besoin de PostgreSQL + Valkey ; les tests d'intégration les démarrent seuls).

```bash
cd ..                                     # racine du dépôt
cp .env.template .env                     # puis adapter les secrets
docker compose up -d postgres pgbouncer valkey
cd backend

uv sync                                   # installe les dépendances
uv run alembic upgrade head               # applique le schéma
make run                                  # → http://localhost:8000/docs
```

Le défaut d'`APP_DATABASE_URL` vise déjà le PgBouncer exposé en local (port
6432) ; ajuster si les identifiants du `.env` changent.

**Tout en conteneurs** — le `docker-compose.yml` racine monte la stack complète
(API, worker, PgBouncer, PostgreSQL, Valkey, RabbitMQ, Mailpit) :

```bash
docker compose up --build                 # → http://localhost:8000/docs
```

## Architecture en un coup d'œil

Le cœur ne dépend de rien ; **tout pointe vers l'intérieur**.

```
┌──────────────────────────────────────────────────────────┐
│  presentation  (FastAPI, Pydantic)     ─ adaptateur driving│
│  infrastructure (SQLAlchemy, Valkey…)  ─ adaptateurs driven│
│        │                                                   │
│        ▼                                                   │
│     application  (use cases, ports)                        │
│        │                                                   │
│        ▼                                                   │
│      domain  (entités, value objects, ports)  ← Python pur │
└──────────────────────────────────────────────────────────┘
```

```
src/task_manager/
├── domain/          # cœur métier pur : entités, value objects, ports, exceptions
├── application/     # use cases (un par action) + ports transverses (cache, smtp…)
├── infrastructure/  # adaptateurs driven : persistance, ORM, messaging, config
├── presentation/    # adaptateurs driving : API HTTP, CLI, worker
└── main.py          # point d'entrée ASGI
```

Chaque couche est **tranchée par bounded context** (`domain/task/`,
`domain/user/`, …). La règle de dépendance est **enforcée par import-linter**
(couches + domaine sans framework) :

```bash
make imports        # ou : uv run lint-imports
```

→ Approfondir : [architecture](docs/cours/01-architecture-hexagonale.md) ·
[le domaine](docs/cours/02-le-domaine.md) ·
[relations entre agrégats](docs/cours/05-relations-entre-agregats.md) ·
[décisions transverses](docs/cours/06-decisions-transverses.md) (erreurs, transactions, DI).

## Commandes

Tout passe par `make` (versions des outils épinglées dans `pyproject.toml`) —
`make help` liste tout :

| Commande            | Effet                                                    |
|---------------------|----------------------------------------------------------|
| `make run`          | Serveur de dev (rechargement à chaud)                    |
| `make worker`       | Worker de notifications (consumer RabbitMQ)              |
| `make test`         | Tous les tests · `make test-unit` / `make test-integration` |
| `make lint`         | ruff + import-linter + mypy strict                       |
| `make format`       | Formate le code (ruff)                                    |
| `make migrate`      | `alembic upgrade head`                                    |
| `make migration m="…"` | Nouvelle révision auto-générée                        |
| `make precommit-install` | Installe les hooks git (ruff, mypy, import-linter) |

`make check` (= `lint` + `test`) reproduit la CI en local.

## Ajouter un use case

1. **Écrire** la classe dans `application/<ctx>/use_cases/` : le constructeur
   reçoit les **ports** nécessaires, `execute(...)` orchestre le domaine et
   renvoie un **DTO** neutre (pas de Pydantic).
2. **Câbler** un provider `get_<use_case>` dans
   `presentation/api/dependencies/<ctx>.py`, réexporté par `dependencies/__init__.py`.
3. **Exposer** une route dans `presentation/api/v1/routers/<ctx>.py` + le schéma
   requête/réponse dans `v1/schemas/<ctx>.py`.
4. **Tester** avec des ports mockés dans `tests/unit/application/` (rapide, sans I/O).

`RenameUser` est un exemple minimal complet (mutation + invalidation de cache).
Pour un **nouveau bounded context** entier, le contexte `user` sert de référence.
→ Recette détaillée : [démarrer un projet](docs/cours/08-demarrer-un-projet.md) ·
[application & use cases](docs/cours/03-application-use-cases.md).

## API

| Méthode | Route                          | Description                       |
|---------|--------------------------------|-----------------------------------|
| POST    | `/api/v1/users`                | Créer un utilisateur              |
| GET     | `/api/v1/users?limit=&offset=` | Lister les utilisateurs (paginé)  |
| GET     | `/api/v1/users/{id}`           | Récupérer un utilisateur (caché)  |
| PATCH   | `/api/v1/users/{id}`           | Renommer un utilisateur           |
| POST    | `/api/v1/users/{id}/tasks`     | Créer une tâche pour ce user (1→n)|
| GET     | `/api/v1/users/{id}/tasks`     | Lister les tâches d'un user       |
| GET     | `/api/v1/tasks?limit=&offset=` | Lister toutes les tâches (paginé) |
| GET     | `/api/v1/tasks/{id}`           | Récupérer une tâche               |
| PATCH   | `/api/v1/tasks/{id}`           | Renommer une tâche                |
| POST    | `/api/v1/tasks/{id}/start`     | Démarrer une tâche                |
| POST    | `/api/v1/tasks/{id}/complete`  | Terminer une tâche                |
| POST    | `/api/v1/tasks/{id}/share`     | Partager (→ notifications worker) |
| DELETE  | `/api/v1/tasks/{id}`           | Supprimer une tâche               |
| GET     | `/health` · `/ready`           | Liveness · readiness (DB + cache) |

Une tâche appartient toujours à un utilisateur (**1→n**) : elle se crée sous la
route imbriquée du propriétaire, et son `owner_id` référence le user.

```bash
USER=$(curl -s -X POST localhost:8000/api/v1/users \
  -H 'content-type: application/json' \
  -d '{"name": "Ada Lovelace", "email": "ada@example.com"}' | jq -r .id)

curl -X POST localhost:8000/api/v1/users/$USER/tasks \
  -H 'content-type: application/json' \
  -d '{"title": "Rédiger le rapport"}'
```

## Déploiement

Le schéma est versionné sous `alembic/`. En Docker, un service `migrate` exécute
`alembic upgrade head` (**connexion directe Postgres**, pas PgBouncer) avant le
démarrage de l'`api` et du `worker`.

```bash
uv run alembic upgrade head                      # applique les migrations
uv run alembic revision --autogenerate -m "…"    # nouvelle révision
```

`APP_INIT_DB=true` reste dispo en local pour un `create_all` rapide sans Alembic
(défaut `false` ; en prod / Docker = Alembic uniquement). La configuration se
fait par variables d'environnement préfixées `APP_` (ou un `.env`) — liste
complète et défauts dans `src/task_manager/infrastructure/config.py`.

## Vers la production

Ce template vise la clarté pédagogique ; pour un service réel, prévoir notamment :
logging structuré + OpenTelemetry/Prometheus et un *correlation id*, et — si les
use cases grossissent — un *Unit of Work* explicite (la frontière transactionnelle
est déjà isolée dans `get_session`).
