from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du projet = dossier contenant `app/`, `alembic/` et `.env`.
# Le chemin est absolu : le chargement ne dépend pas du répertoire courant
# (uvicorn lancé ailleurs, script dans un autre dossier, pytest, Alembic…).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Charge `.env` dans os.environ dès l'import (sans écraser les variables déjà
# définies : l'environnement du shell reste prioritaire).
load_dotenv(ENV_FILE, override=False)

_SYNC_PREFIXES = (
    "postgresql+psycopg2://",
    "postgresql+psycopg://",
    "postgres://",
    "postgresql://",
)


class Settings(BaseSettings):
    """Paramètres de l'application, lus depuis l'environnement / `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Chatbot API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    # Connexion brute, telle que fournie dans .env
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatbot"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Assistant / LLM (OpenRouter via LangChain).
    # La clé n'a pas de valeur par défaut : elle vient exclusivement de `.env`
    # ou de l'environnement, et n'est jamais renvoyée au client.
    openrouter_api_key: str | None = None
    # `minimax/minimax-m3.1-flash:free` a été retiré par OpenRouter le 22/10/2026
    # (fin de la période de lancement). On utilise un modèle gratuit équivalent
    # qui supporte le tool calling. Surchargeable via OPENROUTER_MODEL.
    openrouter_model: str = "openrouter:nvidia/nemotron-3.5-lightning:free"
    # Plafonne la génération : évite les refus « PaymentRequired » des modèles
    # payants (OpenRouter provisionne max_tokens × prix de sortie) et les
    # réponses inutilement longues.
    openrouter_max_tokens: int = 2048

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """URL pour le moteur asynchrone (asyncpg)."""
        for prefix in _SYNC_PREFIXES:
            if self.database_url.startswith(prefix):
                return "postgresql+asyncpg://" + self.database_url[len(prefix) :]
        return self.database_url

    @property
    def sync_database_url(self) -> str:
        """URL pour les outils synchrones (Alembic offline, scripts)."""
        for prefix in _SYNC_PREFIXES:
            if self.database_url.startswith(prefix):
                return "postgresql+psycopg://" + self.database_url[len(prefix) :]
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
