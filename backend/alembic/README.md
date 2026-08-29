# Migrations Alembic

Schéma PostgreSQL versionné pour `task_manager`. L’URL de connexion vient de
`Settings` (`APP_DATABASE_URL`, préfixe `APP_`) — voir `alembic/env.py`.

## Prérequis

1. Se placer dans le dossier **backend** (là où se trouve `alembic.ini`) :

   ```bash
   cd backend
   uv sync
   ```

2. Avoir Postgres joignable depuis l’hôte :

   ```bash
   # depuis la racine du repo
   docker compose up -d postgres
   ```

3. Pointer Alembic vers **Postgres en direct** (`localhost:5432`), pas vers le
   hostname Docker `postgres` (résolution DNS uniquement dans le réseau Compose),
   et de préférence **pas** PgBouncer en mode `transaction` (DDL).

   Le défaut de `Settings` vise `localhost:6432` (PgBouncer). En local, surcharge
   l’URL pour les commandes Alembic :

   ```bash
   export APP_DATABASE_URL="postgresql+asyncpg://task_manager:change-me@localhost:5432/task_manager"
   ```

   (Adapte user / mot de passe / DB selon ton `.env` à la racine du repo.)

   `Settings` charge un fichier `.env` relatif au **cwd**. Depuis `backend/`,
   soit tu exportes `APP_DATABASE_URL`, soit tu places un `.env` dans `backend/`.

## Commandes usuelles

Toujours depuis `backend/` :

```bash
# Appliquer toutes les migrations en attente
uv run alembic upgrade head

# État courant / historique
uv run alembic current
uv run alembic history

# Nouvelle révision à partir des modèles ORM (autogenerate)
uv run alembic revision --autogenerate -m "ajoute colonne X"

# Révision vide (à remplir à la main)
uv run alembic revision -m "description"

# Revenir d’une révision
uv run alembic downgrade -1

# Marquer la DB comme déjà à jour SANS exécuter le SQL
# (ex. schéma créé avant Alembic via create_all)
uv run alembic stamp head
```

## Mettre à jour le schéma (workflow)

1. Modifier les modèles ORM sous
   `src/task_manager/infrastructure/persistence/*/models.py`.
2. Générer une révision :

   ```bash
   APP_DATABASE_URL="postgresql+asyncpg://task_manager:change-me@localhost:5432/task_manager" \
     uv run alembic revision --autogenerate -m "describe le changement"
   ```

3. **Relire** le fichier créé dans `alembic/versions/` (autogenerate n’est pas
   infaillible : index, renommages, données, relations cross-fichiers).
4. Appliquer :

   ```bash
   APP_DATABASE_URL="postgresql+asyncpg://task_manager:change-me@localhost:5432/task_manager" \
     uv run alembic upgrade head
   ```
5. Committer le fichier de révision avec le reste du changement.

## Docker

Au `docker compose up`, le service `migrate` exécute `alembic upgrade head`
contre `postgres:5432` (réseau interne) avant `api` / `worker`. Pas besoin de
lancer Alembic à la main dans ce cas.

## `APP_INIT_DB`

`APP_INIT_DB=true` fait un `create_all` au démarrage de l’API (confort local).
En Docker / prod, laisser `false` : le schéma est piloté uniquement par Alembic.
