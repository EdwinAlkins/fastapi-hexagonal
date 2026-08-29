# Raccourcis de développement du backend.
# Toutes les cibles s'exécutent depuis `backend/`. Lancer `make` (ou `make help`)
# affiche la liste. Les outils passent par `uv run` : versions épinglées par pyproject.

.DEFAULT_GOAL := help

# Passe `m="message"` à `make migration` (ex. make migration m="ajoute colonne x").
m ?= change

.PHONY: help install lint format format-check typecheck imports test test-unit test-integration cov run worker migrate migration check precommit-install precommit

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances (uv sync)
	uv sync

lint: ruff imports typecheck ## Lint complet : ruff + contrats d'imports + mypy

ruff: ## Vérifie le lint (ruff check)
	uv run ruff check .

format: ## Formate le code (ruff format)
	uv run ruff format .

format-check: ## Vérifie le formatage sans modifier
	uv run ruff format --check .

typecheck: ## Vérifie les types (mypy strict)
	uv run mypy

imports: ## Vérifie l'architecture (couches + domaine pur) via import-linter
	uv run lint-imports

test: ## Lance toute la suite de tests
	uv run pytest

test-unit: ## Tests unitaires seulement (rapides, purs)
	uv run pytest tests/unit

test-integration: ## Tests d'intégration (Docker requis : testcontainers)
	uv run pytest tests/integration

cov: ## Tests avec rapport de couverture
	uv run pytest --cov=task_manager

run: ## Serveur de dev (rechargement à chaud) → http://localhost:8000/docs
	uv run uvicorn task_manager.main:app --reload

worker: ## Lance le worker de notifications (consumer RabbitMQ)
	uv run python -m task_manager.presentation.worker

migrate: ## Applique les migrations (alembic upgrade head)
	uv run alembic upgrade head

migration: ## Génère une révision : make migration m="décris le changement"
	uv run alembic revision --autogenerate -m "$(m)"

check: lint test ## CI locale : lint + tests

precommit-install: ## Installe les hooks git pre-commit
	uv run pre-commit install

precommit: ## Exécute les hooks pre-commit sur tous les fichiers
	uv run pre-commit run --all-files
