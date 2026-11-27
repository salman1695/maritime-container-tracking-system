from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration for the shipment tracking microservice."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = Field(default="shipment_service", alias="SERVICE_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    safecube_base_url: str = Field(
        default="https://api.sinay.ai/container-tracking/api/v2",
        alias="SAFECUBE_BASE_URL",
    )
    safecube_api_key: str = Field(default="", alias="SAFECUBE_API_KEY")
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    cache_ttl_seconds: int = Field(default=900, ge=30, le=86400)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()