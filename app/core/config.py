from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NewAPI Credit Logger"
    app_version: str = "0.1.2"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./data/newapi_credit_logger.db"

    log_dir: str = "logs"
    log_level: str = "DEBUG"
    log_rotation: str = "00:00"
    log_retention: str = "30 days"
    log_preview_len: int = 220

    default_poll_interval_seconds: int = 300
    default_request_timeout_seconds: int = 20
    default_request_retries: int = 2

    api_key_encrypt_secret: str = "change-me-in-production"
    admin_password: str = "change-me-admin-password"
    admin_session_secret: str = "change-me-admin-session-secret"

    api_tool_rate_limit_per_minute: int = 30

    default_test_channel: str = "openai_responses"
    default_cli_profile: str = "codex"
    default_openai_base_url: str = "https://api.openai.com"
    default_openai_chat_model: str = "gpt-5.3-codex"
    default_openai_responses_model: str = "gpt-5.3-codex"
    default_gemini_base_url: str = "https://generativelanguage.googleapis.com"
    default_gemini_model: str = "gemini-3-flash-preview"
    default_claude_base_url: str = "https://api.anthropic.com"
    default_claude_model: str = "claude-sonnet-4-6"

    parser_llm_channel: str = "openai_chat"
    parser_llm_base_url: str = ""
    parser_llm_api_key: str = ""
    parser_llm_model: str = ""
    parser_llm_timeout_sec: float = 30.0
    parser_llm_cli_profile: str = "default"

    neko_base_url: str = ""
    neko_base_urls: str = "{}"
    neko_default_site_key: str = ""
    neko_show_balance: bool = True
    neko_show_detail: bool = True
    neko_timeout_sec: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
