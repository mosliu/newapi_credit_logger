from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: str = Field(default="newapi", min_length=1, max_length=30)
    base_url: str = Field(min_length=1, max_length=255)
    key_owner: str = Field(min_length=1, max_length=100)
    remark: str | None = Field(default=None, max_length=500)
    interval_seconds: int = Field(default=60, ge=10, le=86400)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    enabled: bool = True


class SourceCreate(SourceBase):
    api_key: str = Field(min_length=1, max_length=512)


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider_type: str | None = Field(default=None, min_length=1, max_length=30)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    key_owner: str | None = Field(default=None, min_length=1, max_length=100)
    remark: str | None = Field(default=None, max_length=500)
    interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    enabled: bool | None = None


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    api_key_masked: str
    created_at: datetime
    updated_at: datetime
