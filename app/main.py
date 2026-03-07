from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.tasks.scheduler_service import source_scheduler_service
from app.ui.router import router as ui_router

settings = get_settings()
configure_logging(settings)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Application startup")
    source_scheduler_service.start()
    yield
    source_scheduler_service.shutdown()
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api")
    app.include_router(ui_router)

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {"message": "newapi credit logger is running"}

    return app


app = create_app()
