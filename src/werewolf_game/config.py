from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EXAMPLE_APP_TOKEN = "-".join(("replace", "with", "at", "least", "24", "characters"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    runtime_mode: Literal["openai", "demo"] = "openai"
    llm_api_key: SecretStr | None = None
    llm_model_id: str | None = None
    llm_base_url: str | None = None
    llm_timeout: float = Field(default=60, gt=0, le=600)
    llm_trust_env: bool = False
    app_api_token: SecretStr = Field(min_length=24)
    database_url: str = "sqlite+aiosqlite:///./data/werewolf.db"
    cors_origins: list[str] = Field(default_factory=list)
    log_level: str = "INFO"
    max_concurrent_games: int = Field(default=4, ge=1, le=32)
    max_model_concurrency: int = Field(default=8, ge=1, le=64)
    model_max_retries: int = Field(default=2, ge=0, le=5)
    historian_timeout: float = Field(default=600, gt=0, le=3600)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    web_dist_dir: str = "frontend/dist"
    metrics_enabled: bool = True
    max_sse_connections: int = Field(default=100, ge=1, le=10_000)
    run_live_tests: bool = False

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> Settings:
        if self.runtime_mode == "openai" and not all(
            (self.llm_api_key, self.llm_model_id, self.llm_base_url)
        ):
            raise ValueError(
                "openai 模式必须配置 LLM_API_KEY、LLM_MODEL_ID 和 LLM_BASE_URL"
            )
        token = self.app_api_token.get_secret_value()
        if token == EXAMPLE_APP_TOKEN:
            raise ValueError("APP_API_TOKEN 不能使用示例占位值")
        return self
