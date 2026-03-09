from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord


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
                "remark": source.remark,
                "enabled": source.enabled,
                "interval_seconds": source.interval_seconds,
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
