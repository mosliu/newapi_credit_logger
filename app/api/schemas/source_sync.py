from pydantic import BaseModel, Field, field_validator

from app.api.schemas.source import _default_interval_seconds
from app.services.providers.catalog import is_supported_provider_type


class SourceSyncRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=120)
    user_token: str = Field(min_length=1, max_length=512)
    provider_type: str = Field(default="newapi", min_length=1, max_length=30)
    key_owner: str | None = Field(default=None, max_length=100)
    interval_seconds: int = Field(default_factory=_default_interval_seconds, ge=10, le=86400)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return normalized

    @field_validator("user_id", "user_token")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not is_supported_provider_type(normalized):
            raise ValueError("unsupported provider type")
        return normalized

    @field_validator("key_owner")
    @classmethod
    def normalize_key_owner(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SourceSyncResponse(BaseModel):
    run_id: int
    status: str
    base_url: str
    user_id: str
    fetched_count: int
    created_count: int
    skipped_count: int
    failed_count: int
    message: str
    used_endpoint: str
    created_source_names: list[str]
    errors: list[str]
