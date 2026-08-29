# syntax=docker/dockerfile:1

# --- Stage build : résout et installe les dépendances avec uv ---
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Couche de cache : dépendances seules (sans le code applicatif).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Code applicatif + installation du projet.
COPY src ./src
COPY README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage runtime : image légère sans uv ---
FROM python:3.14-slim-bookworm AS runtime

WORKDIR /app

# Copie l'environnement virtuel, le code et le scaffolding Alembic.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# APP_DATABASE_URL est fourni par l'environnement (docker-compose) : l'image ne
# présume pas de la base qu'elle vise.

EXPOSE 8000

# Gunicorn (process manager) + UvicornWorker (ASGI async).
# --workers peut être surchargé via docker-compose (API_WORKERS).
CMD ["gunicorn", "task_manager.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2"]
