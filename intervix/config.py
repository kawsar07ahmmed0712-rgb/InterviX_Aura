from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "InterviX Aura"
    model_provider: str = Field(default="auto", validation_alias="MODEL_PROVIDER")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", validation_alias="GEMINI_MODEL")
    ollama_model: str = Field(default="gemma3:1b", validation_alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    db_path: Path = Field(default=BASE_DIR / "intervix_aura.db", validation_alias="DB_PATH")
    answer_max_chars: int = Field(default=1200, ge=200, le=4000, validation_alias="ANSWER_MAX_CHARS")
    min_questions: int = Field(default=2, ge=1, le=12, validation_alias="MIN_QUESTIONS")
    max_questions: int = Field(default=8, ge=2, le=12, validation_alias="MAX_QUESTIONS")
    provider_timeout_seconds: float = Field(
        default=90.0,
        ge=5.0,
        le=180.0,
        validation_alias="PROVIDER_TIMEOUT_SECONDS",
    )
    provider_health_timeout_seconds: float = Field(
        default=4.0,
        ge=1.0,
        le=15.0,
        validation_alias="PROVIDER_HEALTH_TIMEOUT_SECONDS",
    )
    provider_max_retries: int = Field(default=3, ge=1, le=5, validation_alias="PROVIDER_MAX_RETRIES")
    provider_retry_base_seconds: float = Field(
        default=1.25,
        ge=0.1,
        le=10.0,
        validation_alias="PROVIDER_RETRY_BASE_SECONDS",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        validation_alias="RATE_LIMIT_WINDOW_SECONDS",
    )
    rate_limit_connections: int = Field(
        default=12,
        ge=2,
        le=100,
        validation_alias="RATE_LIMIT_CONNECTIONS",
    )
    rate_limit_messages: int = Field(
        default=40,
        ge=5,
        le=300,
        validation_alias="RATE_LIMIT_MESSAGES",
    )

    @property
    def database_url(self) -> str:
        return str(self.db_path)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
