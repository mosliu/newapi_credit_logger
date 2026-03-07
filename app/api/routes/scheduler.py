from fastapi import APIRouter, HTTPException, status

from app.tasks.scheduler_service import source_scheduler_service

router = APIRouter(prefix="/scheduler")


@router.post("/reload")
async def reload_scheduler_jobs() -> dict[str, int]:
    count = source_scheduler_service.reload_jobs()
    return {"job_count": count}


@router.post("/check-now/{source_id}")
async def check_balance_now(source_id: int) -> dict[str, str]:
    success = source_scheduler_service.collect_now(source_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return {"status": "ok"}
