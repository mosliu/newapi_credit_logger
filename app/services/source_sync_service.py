from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.api.schemas.source_sync import SourceSyncRequest
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.api_key_source import ApiKeySource
from app.models.token_sync_run import TokenSyncRun
from app.services.crypto_service import encrypt_api_key
from app.services.providers.utils import build_request_headers

logger = get_logger("app")

_TOKEN_LIST_ENDPOINTS = (
    "/api/token",
    "/api/token/",
    "/api/tokens",
    "/api/tokens/",
    "/api/token/list",
)
_TOKEN_NAME_KEYS = ("name", "token_name", "display_name", "title", "key_name")
_TOKEN_VALUE_KEYS = ("key", "token", "api_key", "value", "secret", "access_token")


@dataclass(frozen=True)
class _QueryVariant:
    page_key: str
    page_base: int
    size_key: str
    user_key: str

    def build_params(self, *, page: int, page_size: int, user_id: str) -> dict[str, str | int]:
        return {
            self.page_key: page + self.page_base,
            self.size_key: page_size,
            self.user_key: user_id,
        }


_QUERY_VARIANTS = (
    _QueryVariant("p", 0, "size", "user"),
    _QueryVariant("p", 0, "size", "user_id"),
    _QueryVariant("page", 0, "size", "user"),
    _QueryVariant("page", 0, "size", "user_id"),
    _QueryVariant("page", 0, "page_size", "user"),
    _QueryVariant("page", 0, "page_size", "user_id"),
    _QueryVariant("page", 1, "size", "user"),
    _QueryVariant("page", 1, "size", "user_id"),
    _QueryVariant("page", 1, "page_size", "user"),
    _QueryVariant("page", 1, "page_size", "user_id"),
    _QueryVariant("p", 1, "size", "user"),
    _QueryVariant("p", 1, "size", "user_id"),
)


def _pick_message(payload: Any, default: str) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return default


def _extract_list_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    data = payload.get("data", payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "list", "rows", "records", "tokens", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    for key in ("items", "list", "rows", "records", "tokens"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _has_more_pages(payload: Any, rows_count: int, page: int, page_size: int) -> bool:
    if rows_count <= 0:
        return False

    if isinstance(payload, dict):
        data = payload.get("data")
        holder = data if isinstance(data, dict) else payload
        total = holder.get("total")
        if isinstance(total, int) and total >= 0:
            return (page + 1) * page_size < total
        has_more = holder.get("has_more")
        if isinstance(has_more, bool):
            return has_more
        total_pages = holder.get("total_pages")
        if isinstance(total_pages, int) and total_pages > 0:
            return (page + 1) < total_pages

    return rows_count >= page_size


def _query_variants(
    page: int,
    page_size: int,
    user_id: str,
    *,
    preferred: _QueryVariant | None = None,
) -> list[tuple[_QueryVariant, dict[str, str | int]]]:
    variants = (preferred,) if preferred is not None else _QUERY_VARIANTS
    return [
        (
            variant,
            variant.build_params(page=page, page_size=page_size, user_id=user_id),
        )
        for variant in variants
    ]


async def _fetch_tokens_from_upstream(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    user_id: str,
    user_token: str,
    timeout_seconds: int,
    page_size: int = 100,
    max_pages: int = 200,
) -> tuple[list[dict[str, Any]], str]:
    headers = build_request_headers(user_token)
    timeout = httpx.Timeout(connect=8.0, read=float(timeout_seconds), write=10.0, pool=8.0)
    endpoint_errors: list[str] = []

    for endpoint in _TOKEN_LIST_ENDPOINTS:
        endpoint_url = f"{base_url}{endpoint}"
        all_rows: list[dict[str, Any]] = []
        endpoint_supported = False
        selected_variant: _QueryVariant | None = None
        page = 0

        while page < max_pages:
            page_rows: list[dict[str, Any]] | None = None
            page_more = False
            empty_success: tuple[_QueryVariant, bool] | None = None
            query_errors: list[str] = []

            for variant, params in _query_variants(
                page=page,
                page_size=page_size,
                user_id=user_id,
                preferred=selected_variant,
            ):
                try:
                    response = await client.get(endpoint_url, headers=headers, params=params, timeout=timeout)
                except httpx.TimeoutException as exc:
                    query_errors.append(f"timeout params={params}: {exc}")
                    continue
                except httpx.HTTPError as exc:
                    query_errors.append(f"http error params={params}: {exc}")
                    continue

                if response.status_code in {404, 405}:
                    query_errors.append(f"HTTP {response.status_code} params={params}")
                    continue
                if response.status_code in {401, 403}:
                    raise RuntimeError(f"上游鉴权失败（HTTP {response.status_code}），请检查 user_token 是否正确")
                if response.status_code >= 400:
                    query_errors.append(
                        f"HTTP {response.status_code} params={params} body={response.text[:120]}"
                    )
                    continue

                try:
                    payload = response.json()
                except Exception as exc:  # noqa: BLE001
                    query_errors.append(f"invalid json params={params}: {exc}")
                    continue

                success_flag = payload.get("success") if isinstance(payload, dict) else None
                if success_flag in {False, 0, "0", "false", "False"}:
                    query_errors.append(_pick_message(payload, f"upstream success=false params={params}"))
                    continue

                rows = _extract_list_payload(payload)
                endpoint_supported = True
                rows_more = _has_more_pages(payload, rows_count=len(rows), page=page, page_size=page_size)
                if page == 0 and selected_variant is None and not rows:
                    if empty_success is None:
                        empty_success = (variant, rows_more)
                    continue

                selected_variant = variant
                page_rows = rows
                page_more = rows_more
                break

            if page_rows is None and empty_success is not None:
                selected_variant, page_more = empty_success
                page_rows = []

            if page_rows is None:
                if page == 0:
                    endpoint_errors.append(f"{endpoint}: {'; '.join(query_errors)[:360]}")
                break

            if not page_rows:
                break

            all_rows.extend(page_rows)
            if not page_more:
                break
            page += 1

        if endpoint_supported:
            return all_rows, endpoint

    detail = " | ".join(endpoint_errors)[:800]
    raise RuntimeError(f"未能从上游获取 Token 列表，请检查 base_url/user_id/user_token 或接口兼容性。{detail}")


def _extract_token_name(row: dict[str, Any]) -> str:
    for key in _TOKEN_NAME_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_token_value(row: dict[str, Any]) -> str:
    for key in _TOKEN_VALUE_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def list_recent_token_sync_runs(db: Session, *, limit: int = 20) -> list[TokenSyncRun]:
    size = max(1, min(limit, 200))
    return (
        db.query(TokenSyncRun)
        .order_by(TokenSyncRun.id.desc())
        .limit(size)
        .all()
    )


def _build_owner(payload: SourceSyncRequest) -> str:
    if payload.key_owner:
        return payload.key_owner
    return f"user-{payload.user_id}"


def _build_message(*, fetched: int, created: int, skipped: int, failed: int) -> str:
    return f"同步完成：拉取 {fetched}，新增 {created}，跳过 {skipped}，失败 {failed}"


def _persist_failed_sync_run(
    db: Session,
    *,
    payload: SourceSyncRequest,
    message: str,
) -> TokenSyncRun:
    run = TokenSyncRun(
        base_url=payload.base_url,
        user_id=payload.user_id,
        status="failed",
        fetched_count=0,
        created_count=0,
        skipped_count=0,
        failed_count=0,
        message=message[:500],
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


async def sync_sources_from_newapi_user_account(
    *,
    db: Session,
    payload: SourceSyncRequest,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    async def _run(active_client: httpx.AsyncClient) -> dict[str, Any]:
        fetched_rows, used_endpoint = await _fetch_tokens_from_upstream(
            client=active_client,
            base_url=payload.base_url,
            user_id=payload.user_id,
            user_token=payload.user_token,
            timeout_seconds=payload.timeout_seconds,
        )

        owner = _build_owner(payload)
        existing_names = {
            name for (name,) in db.query(ApiKeySource.name).all() if isinstance(name, str) and name.strip()
        }
        batch_names: set[str] = set()
        created_names: list[str] = []
        errors: list[str] = []
        skipped_count = 0
        failed_count = 0

        for index, row in enumerate(fetched_rows, start=1):
            name = _extract_token_name(row)
            token_value = _extract_token_value(row)

            if not name:
                failed_count += 1
                errors.append(f"第 {index} 项缺少 name，已跳过")
                continue

            if not token_value:
                failed_count += 1
                errors.append(f"第 {index} 项（{name}）缺少 token/key 明文，已跳过")
                continue

            if name in existing_names or name in batch_names:
                skipped_count += 1
                continue

            entity = ApiKeySource(
                name=name,
                provider_type=payload.provider_type,
                base_url=payload.base_url,
                api_key_encrypted=encrypt_api_key(token_value),
                key_owner=owner,
                key_account=payload.user_id,
                customer_info=None,
                key_created_at=None,
                fee_amount=None,
                fee_currency=None,
                remark=f"auto-synced by user {payload.user_id}",
                interval_seconds=payload.interval_seconds,
                timeout_seconds=payload.timeout_seconds,
                enabled=payload.enabled,
            )
            db.add(entity)
            batch_names.add(name)
            existing_names.add(name)
            created_names.append(name)

        created_count = len(created_names)
        fetched_count = len(fetched_rows)
        message = _build_message(
            fetched=fetched_count,
            created=created_count,
            skipped=skipped_count,
            failed=failed_count,
        )
        status = "success"
        if failed_count > 0 and created_count > 0:
            status = "partial"
        elif failed_count > 0 and created_count == 0:
            status = "failed"

        run = TokenSyncRun(
            base_url=payload.base_url,
            user_id=payload.user_id,
            status=status,
            fetched_count=fetched_count,
            created_count=created_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            message=message[:500],
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)

        db.commit()

        db.refresh(run)
        logger.info(
            "token sync finished run_id={} base_url={} user_id={} status={} fetched={} created={} skipped={} failed={}",
            run.id,
            payload.base_url,
            payload.user_id,
            status,
            fetched_count,
            created_count,
            skipped_count,
            failed_count,
        )
        return {
            "run_id": run.id,
            "status": status,
            "base_url": payload.base_url,
            "user_id": payload.user_id,
            "fetched_count": fetched_count,
            "created_count": created_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "message": message,
            "used_endpoint": used_endpoint,
            "created_source_names": created_names,
            "errors": errors,
        }

    if client is not None:
        try:
            return await _run(client)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            fail_run = _persist_failed_sync_run(db, payload=payload, message=str(exc))
            logger.warning(
                "token sync failed run_id={} base_url={} user_id={} error={}",
                fail_run.id,
                payload.base_url,
                payload.user_id,
                exc,
            )
            raise

    timeout = max(float(payload.timeout_seconds), 3.0)
    limits = httpx.Limits(max_connections=max(get_settings().scheduler_max_workers, 10))
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as local_client:
        try:
            return await _run(local_client)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            fail_run = _persist_failed_sync_run(db, payload=payload, message=str(exc))
            logger.warning(
                "token sync failed run_id={} base_url={} user_id={} error={}",
                fail_run.id,
                payload.base_url,
                payload.user_id,
                exc,
            )
            raise
