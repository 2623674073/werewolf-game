from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_api_key: SecretStr
    llm_model_id: str
    llm_base_url: str
    llm_timeout: float = Field(default=60, gt=0, le=600)
    app_api_token: SecretStr = Field(min_length=24)
    database_url: str = "sqlite+aiosqlite:///./data/werewolf.db"
    cors_origins: list[str] = Field(default_factory=list)
    log_level: str = "INFO"
    max_concurrent_games: int = Field(default=4, ge=1, le=32)
    max_model_concurrency: int = Field(default=8, ge=1, le=64)
    model_max_retries: int = Field(default=2, ge=0, le=5)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
