from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord
from app.services.crypto_service import decrypt_api_key
from app.services.providers.factory import get_balance_provider

logger = get_logger("scheduler")


def collect_balance_for_source(db: Session, source: ApiKeySource) -> BalanceRecord:
    provider = get_balance_provider(source.provider_type)
    raw_api_key = decrypt_api_key(source.api_key_encrypted)
    result = provider.fetch_balance(
        base_url=source.base_url,
        api_key=raw_api_key,
        timeout_seconds=source.timeout_seconds,
    )

    record = BalanceRecord(
        source_id=source.id,
        success=result.success,
        limit_amount=result.limit_amount,
        usage_amount=result.usage_amount,
        balance=result.balance,
        currency=result.currency,
        http_status=result.http_status,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
        response_excerpt=result.response_excerpt,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        "source_id={} success={} status={} latency_ms={} limit_amount={} usage_amount={} balance={} error={}",
        source.id,
        result.success,
        result.http_status,
        result.latency_ms,
        result.limit_amount,
        result.usage_amount,
        result.balance,
        result.error_message,
    )
    return record
