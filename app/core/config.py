from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NewAPI Credit Logger"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./data/newapi_credit_logger.db"

    log_dir: str = "logs"
    log_level: str = "DEBUG"
    log_rotation: str = "00:00"
    log_retention: str = "30 days"

    default_poll_interval_seconds: int = 60
    default_request_timeout_seconds: int = 20
    default_request_retries: int = 2

    api_key_encrypt_secret: str = "change-me-in-production"
    admin_password: str = "change-me-admin-password"
    admin_session_secret: str = "change-me-admin-session-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
