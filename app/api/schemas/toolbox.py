from typing import Literal

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    raw_text: str = ""


class ApiTestRequest(BaseModel):
    channel: Literal["openai_chat", "openai_responses", "gemini", "claude"]
    base_url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt: str = "请回复：pong"
    timeout_sec: float = Field(default=30, ge=3, le=120)
    cli_profile: str = "default"


class NekoQueryRequest(BaseModel):
    token: str = Field(min_length=1)
    base_url: str = ""
    fetch_balance: bool | None = None
    fetch_detail: bool | None = None
    timeout_sec: float | None = Field(default=None, ge=3, le=120)
