"""
CodeDelta backend – application settings.
All values are read from environment variables (or .env file).
Never hard-code secrets here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "CodeDelta"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g. "http://localhost:5173"
    ALLOWED_ORIGINS: list[AnyHttpUrl] = ["http://localhost:5173"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Database (Supabase Postgres) ──────────────────────────────────────────
    DATABASE_URL: str = ""
    # Direct/session connection for LangGraph checkpointer (port 5432)
    CHECKPOINT_DATABASE_URL: str = ""

    # ── Auth ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str = ""
    ACCESS_TOKEN_MINUTES: int = 15

    # ── LangSmith ────────────────────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "codedelta"

    # ── AI providers ─────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    HUGGINGFACEHUB_API_TOKEN: str = ""
    TAVILY_API_KEY: str = ""

    # ── Google Drive ─────────────────────────────────────────────────────────
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""
    GOOGLE_AUTH_MODE: str = "oauth"  # "oauth" | "service_account"
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REFRESH_TOKEN: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # path to JSON file

    # ── Rate limits ───────────────────────────────────────────────────────────
    MAX_RUNS_PER_DAY: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
