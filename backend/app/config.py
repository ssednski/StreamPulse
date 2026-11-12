from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable with STREAMPULSE_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="STREAMPULSE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./streampulse.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    max_batch_size: int = 1000
    # When set, POST /v1/events requires a matching X-API-Key header.
    ingest_api_key: str | None = None
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
