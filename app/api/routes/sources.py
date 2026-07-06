from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.api.schemas.source_sync import SourceSyncRequest, SourceSyncResponse
from app.db.session import get_db
from app.services.source_service import (
    create_source,
    delete_source,
    get_source,
    list_sources,
    update_source,
)
from app.services.source_sync_service import sync_sources_from_newapi_user_account
from app.tasks.scheduler_service import source_scheduler_service

router = APIRouter(prefix="/sources")


@router.get("", response_model=list[SourceResponse])
async def get_sources(db: Session = Depends(get_db)) -> list[SourceResponse]:
    return list_sources(db)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source_by_id(source_id: int, db: Session = Depends(get_db)) -> SourceResponse:
    result = get_source(db, source_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return result


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item(payload: SourceCreate, db: Session = Depends(get_db)) -> SourceResponse:
    try:
        result = create_source(db, payload)
        source_scheduler_service.reload_jobs()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="source name already exists") from exc


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source_item(
    source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)
) -> SourceResponse:
    try:
        result = update_source(db, source_id, payload)
        source_scheduler_service.reload_jobs()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="source name already exists") from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return result


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_item(source_id: int, db: Session = Depends(get_db)) -> None:
    deleted = delete_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    source_scheduler_service.reload_jobs()


@router.post("/sync/newapi-user", response_model=SourceSyncResponse)
async def sync_sources_from_newapi_user(
    payload: SourceSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SourceSyncResponse:
    client = getattr(request.app.state, "http_client", None)
    try:
        result = await sync_sources_from_newapi_user_account(
            db=db,
            payload=payload,
            client=client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if result["created_count"] > 0:
        source_scheduler_service.reload_jobs()
    return SourceSyncResponse.model_validate(result)
