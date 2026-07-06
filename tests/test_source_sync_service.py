import asyncio
from typing import Any

import httpx

from app.api.schemas.source_sync import SourceSyncRequest
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.api_key_source import ApiKeySource
from app.models.token_sync_run import TokenSyncRun
from app.services.source_sync_service import sync_sources_from_newapi_user_account


def _reset_db_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _json_response(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com/api/token")
    return httpx.Response(status_code=status_code, json=payload, request=request)


class _FakeTokenClient:
    def __init__(self, pages: dict[int, list[dict[str, Any]]], *, total: int | None = None) -> None:
        self.pages = pages
        self.total = total
        self.calls: list[dict[str, Any]] = []

    async def get(self, _url: str, *, headers=None, params=None, timeout=None) -> httpx.Response:
        query = dict(params or {})
        self.calls.append(query)

        if "page" in query and "size" in query and query.get("user") == "1001":
            page = int(query["page"])
            rows = self.pages.get(page, [])
            data: dict[str, Any] = {"items": rows}
            if self.total is not None:
                data["total"] = self.total
            else:
                data["has_more"] = page < max(self.pages)
            return _json_response({"success": True, "data": data})

        if query.get("p") == 0:
            return _json_response({"success": False, "message": "unsupported p pagination"})

        return _json_response({"success": False, "message": "unsupported query variant"})


def test_sync_sources_uses_stable_one_based_pagination_variant() -> None:
    _reset_db_schema()
    client = _FakeTokenClient(
        pages={
            0: [],
            1: [
                {"name": "token-a", "key": "sk-token-a-1234567890"},
                {"name": "token-b", "key": "sk-token-b-1234567890"},
            ],
            2: [{"name": "token-c", "key": "sk-token-c-1234567890"}],
        }
    )
    payload = SourceSyncRequest(
        base_url="https://example.com",
        user_id="1001",
        user_token="sk-user-token-123456",
        provider_type="newapi",
        interval_seconds=60,
        timeout_seconds=10,
        enabled=True,
    )

    with SessionLocal() as db:
        result = asyncio.run(
            sync_sources_from_newapi_user_account(db=db, payload=payload, client=client)
        )
        names = [
            name
            for (name,) in db.query(ApiKeySource.name).order_by(ApiKeySource.id.asc()).all()
        ]
        run = db.query(TokenSyncRun).order_by(TokenSyncRun.id.desc()).first()

    assert result["status"] == "success"
    assert result["fetched_count"] == 3
    assert result["created_count"] == 3
    assert result["created_source_names"] == ["token-a", "token-b", "token-c"]
    assert names == ["token-a", "token-b", "token-c"]
    assert run is not None
    assert run.status == "success"
    assert [call["page"] for call in client.calls if "page" in call and "size" in call] == [
        0,
        0,
        1,
        2,
    ]


def test_sync_sources_allows_empty_upstream_token_list() -> None:
    _reset_db_schema()
    client = _FakeTokenClient(pages={0: []}, total=0)
    payload = SourceSyncRequest(
        base_url="https://example.com",
        user_id="1001",
        user_token="sk-user-token-123456",
        provider_type="newapi",
        interval_seconds=60,
        timeout_seconds=10,
        enabled=True,
    )

    with SessionLocal() as db:
        result = asyncio.run(
            sync_sources_from_newapi_user_account(db=db, payload=payload, client=client)
        )
        source_count = db.query(ApiKeySource).count()
        run = db.query(TokenSyncRun).order_by(TokenSyncRun.id.desc()).first()

    assert result["status"] == "success"
    assert result["fetched_count"] == 0
    assert result["created_count"] == 0
    assert result["skipped_count"] == 0
    assert source_count == 0
    assert run is not None
    assert run.status == "success"
