from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.scheduler import router as scheduler_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(sources_router, tags=["sources"])
api_router.include_router(scheduler_router, tags=["scheduler"])
