import asyncio

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


def _reset_db_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_neko_query_variant_newapi_returns_models_and_raw_response(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if url.endswith("/api/user/self"):
            return {
                "data": {
                    "name": "pytest-token",
                    "quota": 20,
                    "used_quota": 5,
                    "currency": "USD",
                }
            }
        if "/api/log/token" in url:
            return {
                "success": True,
                "data": [
                    {
                        "created_at": 1710000000,
                        "token_name": "pytest-token",
                        "model_name": "gpt-4o-mini",
                        "prompt_tokens": 12,
                        "completion_tokens": 6,
                        "quota": 0.08,
                        "content": "ok",
                    }
                ],
            }
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {
                "object": "list",
                "data": [
                    {
                        "id": "gpt-4o-mini",
                        "owned_by": "openai",
                        "object": "model",
                        "created": 1710000000,
                        "supported_endpoint_types": ["chat/completions", "responses"],
                    }
                ],
            }
        raise RuntimeError(f"unexpected url: {url}")

    monkeypatch.setattr(m, "_get_json", fake_get_json)

    config = m.NekoToolConfig(
        enabled=True,
        show_balance=True,
        show_detail=True,
        base_urls={},
        default_site_key="",
        timeout_sec=30.0,
    )

    result = asyncio.run(
        m.query_neko_token(
            client=None,
            config=config,
            token="sk-test-1234567890",
            base_url="https://example.com",
            variant="newapi",
            fetch_balance=True,
            fetch_detail=True,
            timeout_sec=10,
            cli_profile="codex",
            log_preview_len=220,
        )
    )

    assert any(url.endswith("/api/user/self") for url in called_urls)
    assert any("/api/log/token" in url for url in called_urls)
    assert any(url.endswith("/v1/models") or url.endswith("/models") for url in called_urls)

    assert result["errors"] == []
    assert result["rawResponse"]["userSelf"]["data"]["name"] == "pytest-token"
    assert result["rawResponse"]["logs"]["data"][0]["model_name"] == "gpt-4o-mini"
    assert result["rawResponse"]["models"]["data"][0]["id"] == "gpt-4o-mini"
    assert result["models"] == [
        {
            "id": "gpt-4o-mini",
            "ownedBy": "openai",
            "object": "model",
            "created": 1710000000,
            "supportedEndpointTypes": ["chat/completions", "responses"],
        }
    ]


def test_neko_query_variant_legacy_returns_models_and_raw_response(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if "dashboard/billing/subscription" in url:
            return {"hard_limit_usd": 10, "currency": "USD"}
        if "dashboard/billing/usage" in url:
            return {"total_usage": 100}
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {
                "data": [
                    {
                        "id": "claude-sonnet-4-6",
                        "owned_by": "anthropic",
                        "object": "model",
                        "created": 1711000000,
                        "supported_endpoint_types": ["chat/completions"],
                    }
                ]
            }
        raise RuntimeError(f"unexpected url: {url}")

    monkeypatch.setattr(m, "_get_json", fake_get_json)

    config = m.NekoToolConfig(
        enabled=True,
        show_balance=True,
        show_detail=False,
        base_urls={},
        default_site_key="",
        timeout_sec=30.0,
    )

    result = asyncio.run(
        m.query_neko_token(
            client=None,
            config=config,
            token="sk-test-1234567890",
            base_url="https://example.com",
            variant="newapi_legacy",
            fetch_balance=True,
            fetch_detail=False,
            timeout_sec=10,
            cli_profile="codex",
            log_preview_len=220,
        )
    )

    assert any("dashboard/billing/subscription" in url for url in called_urls)
    assert any("dashboard/billing/usage" in url for url in called_urls)
    assert any(url.endswith("/v1/models") or url.endswith("/models") for url in called_urls)

    assert result["errors"] == []
    assert result["rawResponse"]["subscription"]["hard_limit_usd"] == 10
    assert result["rawResponse"]["usage"]["total_usage"] == 100
    assert result["rawResponse"]["models"]["data"][0]["id"] == "claude-sonnet-4-6"
    assert result["models"][0]["id"] == "claude-sonnet-4-6"


def test_ui_home_contains_neko_models_and_raw_response_sections() -> None:
    _reset_db_schema()
    client = TestClient(app)

    response = client.get("/ui?tab=neko-query")

    assert response.status_code == 200
    assert "模型列表" in response.text
    assert "原始返回" in response.text
    assert "models (/v1/models)" in response.text
