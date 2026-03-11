from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord


def _reset_db_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health_and_ready() -> None:
    _reset_db_schema()
    client = TestClient(app)

    health = client.get("/api/health")
    ready = client.get("/api/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_source_crud_and_manual_collect() -> None:
    _reset_db_schema()
    client = TestClient(app)

    payload = {
        "name": "pytest-source",
        "provider_type": "newapi",
        "base_url": "http://127.0.0.1:9",
        "api_key": "sk-pytest-1234567890",
        "key_owner": "pytest-owner",
        "key_account": "pytest-account",
        "customer_info": "pytest-customer",
        "key_created_at": "2026-01-01T08:30:00+08:00",
        "fee_amount": "99.90",
        "fee_currency": "CNY",
        "remark": "pytest remark",
        "interval_seconds": 60,
        "timeout_seconds": 2,
        "enabled": True,
    }

    created = client.post("/api/sources", json=payload)
    assert created.status_code == 201
    source_id = created.json()["id"]
    assert created.json()["api_key_masked"].startswith("sk-p")
    assert created.json()["key_account"] == "pytest-account"
    assert created.json()["customer_info"] == "pytest-customer"
    assert str(created.json()["fee_amount"]) in {"99.9", "99.90"}
    assert created.json()["fee_currency"] == "CNY"
    assert created.json()["key_created_at"].startswith("2026-01-01T08:30:00")

    collected = client.post(f"/api/scheduler/check-now/{source_id}")
    assert collected.status_code == 200

    listed = client.get("/api/sources")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    with SessionLocal() as db:
        count = db.query(BalanceRecord).filter(BalanceRecord.source_id == source_id).count()
        assert count >= 1

    deleted = client.delete(f"/api/sources/{source_id}")
    assert deleted.status_code == 204


def test_public_key_fragment_search() -> None:
    _reset_db_schema()
    client = TestClient(app)

    first_payload = {
        "name": "search-source-1",
        "provider_type": "newapi",
        "base_url": "http://127.0.0.1:9",
        "api_key": "sk-prefix-search-abcdef123456",
        "key_owner": "owner-1",
        "interval_seconds": 60,
        "timeout_seconds": 2,
        "enabled": True,
    }
    second_payload = {
        "name": "search-source-2",
        "provider_type": "newapi",
        "base_url": "http://127.0.0.1:9",
        "api_key": "sk-another-search-xyz999999",
        "key_owner": "owner-2",
        "interval_seconds": 60,
        "timeout_seconds": 2,
        "enabled": True,
    }

    first_created = client.post("/api/sources", json=first_payload)
    assert first_created.status_code == 201
    first_source_id = first_created.json()["id"]
    assert client.post("/api/sources", json=second_payload).status_code == 201

    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO balance_record
                (source_id, success, limit_amount, usage_amount, balance, currency)
                VALUES (:source_id, 1, :limit_amount, :usage_amount, :balance, :currency)
                """
            ),
            {
                "source_id": first_source_id,
                "limit_amount": 100.5,
                "usage_amount": 33.2,
                "balance": 67.3,
                "currency": "USD",
            },
        )
        db.commit()

    by_prefix = client.get("/ui/key-search", params={"key_fragment": "sk-prefix-search"})
    assert by_prefix.status_code == 200
    assert "search-source-1" in by_prefix.text
    assert "前缀匹配" in by_prefix.text
    assert "Key额度" in by_prefix.text
    assert "Key余额" in by_prefix.text
    assert "最新使用量" in by_prefix.text
    assert "100.5" in by_prefix.text
    assert "67.3" in by_prefix.text
    assert "33.2" in by_prefix.text

    by_suffix = client.get("/ui/key-search", params={"key_fragment": "abcdef123456"})
    assert by_suffix.status_code == 200
    assert "search-source-1" in by_suffix.text
    assert "后缀匹配" in by_suffix.text

    too_short = client.get("/ui/key-search", params={"key_fragment": "12345"})
    assert too_short.status_code == 200
    assert "至少 12 位 key 片段" in too_short.text


def test_public_home_and_tool_config() -> None:
    _reset_db_schema()
    client = TestClient(app)

    home = client.get("/ui")
    assert home.status_code == 200
    assert "登记Key查询（片段匹配）" in home.text
    assert "API 可用性测试工具" in home.text
    assert "API 可用性测试" in home.text
    assert "API Key 查询" in home.text
    assert "v0.1.2" in home.text
    assert 'id="homeNekoQuery" class="home-tab-panel active"' in home.text

    home_neko = client.get("/ui", params={"tab": "neko-query"})
    assert home_neko.status_code == 200
    assert 'id="homeNekoQuery" class="home-tab-panel active"' in home_neko.text

    home_compat = client.get("/ui", params={"tab": "api-tools"})
    assert home_compat.status_code == 200
    assert 'id="homeApiTest" class="home-tab-panel active"' in home_compat.text

    config = client.get("/api/config")
    assert config.status_code == 200
    payload = config.json()
    assert payload["ok"] is True
    assert "defaults" in payload
    assert "llmParser" in payload
    assert "nekoTool" in payload


def test_public_neko_query_smoke(monkeypatch) -> None:
    _reset_db_schema()

    from app.api.routes import public_tools as public_tools_module

    async def fake_query_neko_token(**kwargs):
        return {
            "ok": True,
            "variant": kwargs.get("variant", ""),
            "baseUrl": kwargs.get("base_url", ""),
            "tokenMasked": "sk-***",
            "tokenValid": True,
            "tokenInfo": None,
            "logs": [],
            "stats": {
                "logCount": 0,
                "totalQuota": 0.0,
                "totalPromptTokens": 0,
                "totalCompletionTokens": 0,
                "models": {},
            },
            "errors": [],
        }

    monkeypatch.setattr(public_tools_module, "query_neko_token", fake_query_neko_token)

    # This endpoint depends on resources created in FastAPI lifespan (e.g. app.state.http_client).
    with TestClient(app) as client:
        resp = client.post(
            "/api/neko/query",
            json={
                "token": "sk-test-1234567890",
                "base_url": "https://example.com",
                "variant": "newapi_legacy",
                "fetch_balance": True,
                "fetch_detail": False,
                "timeout_sec": 10,
            },
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["variant"] == "newapi_legacy"
