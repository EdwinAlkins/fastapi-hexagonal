"""Configuration de l'application, chargée depuis l'environnement / ``.env``."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(StrEnum):
    """Niveaux de log acceptés (validation par Pydantic à la construction)."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Paramètres applicatifs (surchargables par variables d'environnement)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "Task Manager"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # URL de la base (async). Assemblée dans ``.env`` (``APP_DATABASE_URL``) par
    # interpolation des composants ``POSTGRES_*`` / ``PGBOUNCER_PORT``, ou fournie
    # directement en variable d'environnement (le service ``api`` la reçoit de
    # docker-compose). Pas de défaut, volontairement : aucun identifiant en dur, et
    # pas de fallback qui divergerait silencieusement du ``.env``.
    # ``prepared_statement_cache_size=0`` est requis dès qu'on passe par PgBouncer
    # en mode transaction (cf. ``persistence.database.create_engine``).
    database_url: SecretStr
    echo_sql: bool = False
    # ``create_all`` au démarrage : pratique en local. Défaut ``False`` pour
    # éviter un schéma hors migrations en prod / Docker (Alembic).
    init_db: bool = False
    cache_ttl: int = 300  # 5 minutes par défaut
    # ``SecretStr`` : une URL Redis de production porte souvent un mot de passe
    # (``redis://user:pass@host``), qui ne doit jamais atterrir dans les logs.
    redis_url: SecretStr
    log_level: LogLevel = LogLevel.INFO
    # Pool SQLAlchemy. Configurable car il se cumule avec le pool PgBouncer placé
    # devant Postgres : dimensionner ``db_pool_size`` × nombre de process en tenant
    # compte de ``max_client_conn`` du pooler.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_from_email: str = "noreply@taskmanager.com"
    # URL du broker. Assemblée dans ``.env`` (``APP_RABBITMQ_URL``) par interpolation
    # des ``RABBITMQ_*``. Pas de défaut, pour la même raison que ``database_url`` —
    # et l'utilisateur ``guest`` n'existe pas sur le broker provisionné.
    rabbitmq_url: SecretStr
    exchange_name: str = "task_events"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Point d'accès unique à la configuration (mémoïsé)."""
    return Settings()
