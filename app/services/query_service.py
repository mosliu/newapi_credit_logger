from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord
from app.services.crypto_service import decrypt_api_key, mask_api_key


def list_source_dashboard(db: Session, key_owner: str | None = None) -> list[dict]:
    query = db.query(ApiKeySource).order_by(ApiKeySource.id.desc())
    if key_owner:
        query = query.filter(ApiKeySource.key_owner.ilike(f"%{key_owner}%"))

    sources = query.all()
    rows: list[dict] = []
    for source in sources:
        latest = (
            db.query(BalanceRecord)
            .filter(BalanceRecord.source_id == source.id)
            .order_by(BalanceRecord.checked_at.desc(), BalanceRecord.id.desc())
            .first()
        )
        rows.append(
            {
                "id": source.id,
                "name": source.name,
                "provider_type": source.provider_type,
                "base_url": source.base_url,
                "key_owner": source.key_owner,
                "key_account": source.key_account,
                "customer_info": source.customer_info,
                "key_created_at": source.key_created_at,
                "fee_amount": source.fee_amount,
                "fee_currency": source.fee_currency,
                "remark": source.remark,
                "enabled": source.enabled,
                "interval_seconds": source.interval_seconds,
                "timeout_seconds": source.timeout_seconds,
                "latest_success": latest.success if latest else None,
                "latest_limit_amount": latest.limit_amount if latest else None,
                "latest_usage_amount": latest.usage_amount if latest else None,
                "latest_balance": latest.balance if latest else None,
                "latest_currency": latest.currency if latest else None,
                "latest_checked_at": latest.checked_at if latest else None,
                "latest_error": latest.error_message if latest else None,
            }
        )
    return rows


def list_source_balance_changes(
    db: Session,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[dict]:
    sources = db.query(ApiKeySource).order_by(ApiKeySource.id.desc()).all()
    grouped: dict[int, list[BalanceRecord]] = defaultdict(list)

    records = (
        db.query(BalanceRecord)
        .filter(BalanceRecord.checked_at >= window_start)
        .filter(BalanceRecord.checked_at <= window_end)
        .filter(BalanceRecord.success.is_(True))
        .filter(BalanceRecord.balance.isnot(None))
        .order_by(BalanceRecord.source_id.asc(), BalanceRecord.checked_at.asc(), BalanceRecord.id.asc())
        .all()
    )
    for record in records:
        grouped[record.source_id].append(record)

    rows: list[dict] = []
    for source in sources:
        bucket = grouped.get(source.id, [])
        first = bucket[0] if bucket else None
        last = bucket[-1] if bucket else None

        delta_balance = None
        if first is not None and last is not None and len(bucket) >= 2:
            try:
                delta_balance = last.balance - first.balance
            except Exception:  # noqa: BLE001
                delta_balance = None

        rows.append(
            {
                "id": source.id,
                "name": source.name,
                "key_owner": source.key_owner,
                "key_account": source.key_account,
                "provider_type": source.provider_type,
                "currency": last.currency if last else None,
                "point_count": len(bucket),
                "first_checked_at": first.checked_at if first else None,
                "first_balance": first.balance if first else None,
                "last_checked_at": last.checked_at if last else None,
                "last_balance": last.balance if last else None,
                "delta_balance": delta_balance,
            }
        )
    return rows


def search_sources_by_key_fragment(db: Session, key_fragment: str) -> tuple[list[dict], str | None]:
    fragment = key_fragment.strip()
    if not fragment:
        return [], None
    if len(fragment) < 12:
        return [], "请输入至少 12 位 key 片段（前缀/后缀匹配更安全、更易定位）。"

    rows: list[dict] = []
    for source in db.query(ApiKeySource).order_by(ApiKeySource.id.desc()).all():
        try:
            raw_api_key = decrypt_api_key(source.api_key_encrypted)
        except Exception:  # noqa: BLE001
            continue

        score = _match_score(raw_api_key, fragment)
        if score <= 0:
            continue
        latest = (
            db.query(BalanceRecord)
            .filter(BalanceRecord.source_id == source.id)
            .order_by(BalanceRecord.checked_at.desc(), BalanceRecord.id.desc())
            .first()
        )

        rows.append(
            {
                "id": source.id,
                "name": source.name,
                "key_owner": source.key_owner,
                "api_key_masked": mask_api_key(raw_api_key),
                "match_hint": _match_hint(raw_api_key, fragment),
                "latest_limit_amount": latest.limit_amount if latest else None,
                "latest_usage_amount": latest.usage_amount if latest else None,
                "latest_balance": latest.balance if latest else None,
                "score": score,
            }
        )

    rows.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    for row in rows:
        row.pop("score", None)
    return rows, None


def _match_score(raw_api_key: str, fragment: str) -> int:
    if len(fragment) >= 12 and raw_api_key.startswith(fragment):
        return 300 + len(fragment)
    if len(fragment) >= 12 and raw_api_key.endswith(fragment):
        return 200 + len(fragment)
    if len(fragment) >= 12 and fragment in raw_api_key:
        return 100 + len(fragment)
    return 0


def _match_hint(raw_api_key: str, fragment: str) -> str:
    if len(fragment) >= 12 and raw_api_key.startswith(fragment):
        return "前缀匹配"
    if len(fragment) >= 12 and raw_api_key.endswith(fragment):
        return "后缀匹配"
    if fragment in raw_api_key:
        return "片段包含匹配"
    return "未匹配"


def get_source_detail(
    db: Session,
    source_id: int,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[ApiKeySource | None, list[BalanceRecord]]:
    source = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
    if source is None:
        return None, []

    end_time = end_at or datetime.utcnow()
    start_time = start_at or (end_time - timedelta(hours=24))
    query = (
        db.query(BalanceRecord)
        .filter(BalanceRecord.source_id == source_id)
        .filter(BalanceRecord.checked_at >= start_time)
        .filter(BalanceRecord.checked_at <= end_time)
        .order_by(BalanceRecord.checked_at.desc(), BalanceRecord.id.desc())
    )
    return source, query.limit(500).all()


def build_chart_points(records: list[BalanceRecord]) -> list[dict]:
    points: list[dict] = []
    for item in reversed(records):
        if not item.success or item.balance is None:
            continue
        value = float(item.balance) if isinstance(item.balance, Decimal) else item.balance
        points.append(
            {
                "time": item.checked_at.isoformat(),
                "limit_amount": float(item.limit_amount) if item.limit_amount is not None else None,
                "usage_amount": float(item.usage_amount) if item.usage_amount is not None else None,
                "balance": value,
            }
        )
    return points
