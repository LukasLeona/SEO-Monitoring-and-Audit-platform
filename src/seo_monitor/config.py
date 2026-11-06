from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SEO_",
        extra="ignore",
    )

    app_name: str = "SEO Monitoring and Audit Platform"
    app_env: str = "development"
    log_level: str = "INFO"
    api_key: SecretStr | None = None
    cors_origins: str = ""
    webhook_url: str | None = None
    webhook_secret: SecretStr | None = None
    webhook_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    database_path: str = "seo_monitor.db"
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    max_response_bytes: int = Field(default=5_000_000, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.25, ge=0, le=10)
    user_agent: str = (
        "SEOMonitorBot/0.1 (+https://github.com/LukasLeona/SEO-Monitoring-and-Audit-platform)"
    )
    max_crawl_pages: int = Field(default=25, ge=1, le=250)
    crawl_concurrency: int = Field(default=5, ge=1, le=20)
    monitor_poll_seconds: int = Field(default=60, ge=5, le=3600)
    allow_private_hosts: bool = False
    gsc_credentials_file: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
