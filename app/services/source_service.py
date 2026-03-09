from sqlalchemy.orm import Session

from app.api.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.models.api_key_source import ApiKeySource
from app.services.crypto_service import decrypt_api_key, encrypt_api_key, mask_api_key


def _to_response(entity: ApiKeySource) -> SourceResponse:
    raw_api_key = decrypt_api_key(entity.api_key_encrypted)
    return SourceResponse.model_validate(
        {
            "id": entity.id,
            "name": entity.name,
            "provider_type": entity.provider_type,
            "base_url": entity.base_url,
            "key_owner": entity.key_owner,
            "key_account": entity.key_account,
            "customer_info": entity.customer_info,
            "key_created_at": entity.key_created_at,
            "fee_amount": entity.fee_amount,
            "fee_currency": entity.fee_currency,
            "remark": entity.remark,
            "interval_seconds": entity.interval_seconds,
            "timeout_seconds": entity.timeout_seconds,
            "enabled": entity.enabled,
            "api_key_masked": mask_api_key(raw_api_key),
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }
    )


def list_sources(db: Session) -> list[SourceResponse]:
    rows = db.query(ApiKeySource).order_by(ApiKeySource.id.desc()).all()
    return [_to_response(item) for item in rows]


def get_source(db: Session, source_id: int) -> SourceResponse | None:
    row = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
    if row is None:
        return None
    return _to_response(row)


def create_source(db: Session, payload: SourceCreate) -> SourceResponse:
    entity = ApiKeySource(
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        api_key_encrypted=encrypt_api_key(payload.api_key),
        key_owner=payload.key_owner,
        key_account=payload.key_account,
        customer_info=payload.customer_info,
        key_created_at=payload.key_created_at,
        fee_amount=payload.fee_amount,
        fee_currency=payload.fee_currency,
        remark=payload.remark,
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
        enabled=payload.enabled,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return _to_response(entity)


def update_source(db: Session, source_id: int, payload: SourceUpdate) -> SourceResponse | None:
    entity = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
    if entity is None:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    api_key = update_data.pop("api_key", None)
    if api_key:
        entity.api_key_encrypted = encrypt_api_key(api_key)

    for key, value in update_data.items():
        setattr(entity, key, value)

    db.add(entity)
    db.commit()
    db.refresh(entity)
    return _to_response(entity)


def delete_source(db: Session, source_id: int) -> bool:
    entity = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
    if entity is None:
        return False
    db.delete(entity)
    db.commit()
    return True
