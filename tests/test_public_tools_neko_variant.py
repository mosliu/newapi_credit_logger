import asyncio


def test_neko_query_variant_legacy_uses_dashboard_billing(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if "dashboard/billing/subscription" in url:
            return {"hard_limit_usd": 10, "currency": "USD"}
        if "dashboard/billing/usage" in url:
            return {"total_usage": 100}  # cents/fen
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
            client=None,  # not used by fake_get_json
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
    assert not any("/api/user/self" in url for url in called_urls)

    token_info = result.get("tokenInfo") or {}
    assert token_info.get("totalGranted") == 10.0
    assert token_info.get("totalUsed") == 1.0
    assert token_info.get("totalAvailable") == 9.0


def test_neko_query_variant_legacy_ignores_detail_query(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if "/api/log/token" in url:
            raise AssertionError("newapi_legacy must not query /api/log/token")
        if "dashboard/billing/subscription" in url:
            return {"hard_limit_usd": 10, "currency": "USD"}
        if "dashboard/billing/usage" in url:
            return {"total_usage": 100}
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
            client=None,  # not used by fake_get_json
            config=config,
            token="sk-test-1234567890",
            base_url="https://example.com",
            variant="newapi_legacy",
            fetch_balance=True,
            fetch_detail=True,
            timeout_sec=10,
            cli_profile="codex",
            log_preview_len=220,
        )
    )

    assert any("dashboard/billing/subscription" in url for url in called_urls)
    assert any("dashboard/billing/usage" in url for url in called_urls)
    assert result.get("fetchDetail") is False


def test_neko_query_variant_newapi_uses_user_self(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if url.endswith("/api/user/self"):
            return {
                "data": {
                    "name": "pytest-token",
                    "quota": 10,
                    "used_quota": 1,
                    "currency": "USD",
                }
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
            client=None,  # not used by fake_get_json
            config=config,
            token="sk-test-1234567890",
            base_url="https://example.com",
            variant="newapi",
            fetch_balance=True,
            fetch_detail=False,
            timeout_sec=10,
            cli_profile="codex",
            log_preview_len=220,
        )
    )

    assert any(url.endswith("/api/user/self") for url in called_urls)

    token_info = result.get("tokenInfo") or {}
    assert token_info.get("tokenName") == "pytest-token"
    assert token_info.get("totalGranted") == 10.0
    assert token_info.get("totalUsed") == 1.0
    assert token_info.get("totalAvailable") == 9.0


def test_neko_query_variant_legacy_still_calls_usage_when_subscription_fails(monkeypatch) -> None:
    from app.services import public_tool_service as m

    called_urls: list[str] = []

    async def fake_get_json(**kwargs):
        url = kwargs.get("url", "")
        called_urls.append(url)
        if "dashboard/billing/subscription" in url:
            raise RuntimeError("HTTP 401 Unauthorized: token exhausted")
        if "dashboard/billing/usage" in url:
            return {"total_usage": 100}
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
            client=None,  # not used by fake_get_json
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
    assert result.get("ok") is False
    assert result.get("tokenValid") is False
    assert isinstance(result.get("errors"), list) and len(result["errors"]) >= 1
