from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.admin.router import router as admin_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.admin_auth_service import is_admin_authenticated
from app.tasks.scheduler_service import source_scheduler_service
from app.ui.router import router as ui_router

settings = get_settings()
configure_logging(settings)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    app.state.http_client = httpx.AsyncClient()
    source_scheduler_service.start()
    yield
    source_scheduler_service.shutdown()
    await app.state.http_client.aclose()
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def admin_auth_middleware(request, call_next):
        path = request.url.path
        if path.startswith("/admin") and path not in {"/admin/login", "/admin/logout"}:
            if not is_admin_authenticated(request):
                return RedirectResponse(url="/admin/login", status_code=303)
        return await call_next(request)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.admin_session_secret,
        session_cookie="admin_session",
        same_site="lax",
        https_only=False,
    )

    app.include_router(api_router, prefix="/api")
    app.include_router(ui_router)
    app.include_router(admin_router)

    @app.get("/", tags=["system"])
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui", status_code=303)

    return app


app = create_app()
