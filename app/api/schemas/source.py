from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import field_validator

from app.core.config import get_settings
from app.services.providers.catalog import is_supported_provider_type


def _default_interval_seconds() -> int:
    return get_settings().default_poll_interval_seconds


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: str = Field(default="newapi", min_length=1, max_length=30)
    base_url: str = Field(min_length=1, max_length=255)
    key_owner: str = Field(min_length=1, max_length=100)
    key_account: str | None = Field(default=None, max_length=120)
    customer_info: str | None = Field(default=None, max_length=255)
    key_created_at: datetime | None = None
    fee_amount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    fee_currency: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=500)
    interval_seconds: int = Field(default_factory=_default_interval_seconds, ge=10, le=86400)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    enabled: bool = True

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not is_supported_provider_type(normalized):
            raise ValueError("unsupported provider type")
        return normalized


class SourceCreate(SourceBase):
    api_key: str = Field(min_length=1, max_length=512)


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider_type: str | None = Field(default=None, min_length=1, max_length=30)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    key_owner: str | None = Field(default=None, min_length=1, max_length=100)
    key_account: str | None = Field(default=None, max_length=120)
    customer_info: str | None = Field(default=None, max_length=255)
    key_created_at: datetime | None = None
    fee_amount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    fee_currency: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=500)
    interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    enabled: bool | None = None

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not is_supported_provider_type(normalized):
            raise ValueError("unsupported provider type")
        return normalized


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    api_key_masked: str
    created_at: datetime
    updated_at: datetime
