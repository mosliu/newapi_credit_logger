from secrets import compare_digest

from fastapi import Request

from app.core.config import get_settings

ADMIN_SESSION_KEY = "admin_authenticated"


def is_admin_authenticated(request: Request) -> bool:
    if "session" not in request.scope:
        return False
    return bool(request.session.get(ADMIN_SESSION_KEY))


def verify_admin_password(password: str) -> bool:
    settings = get_settings()
    return bool(settings.admin_password) and compare_digest(password, settings.admin_password)


def mark_admin_authenticated(request: Request) -> None:
    if "session" not in request.scope:
        return
    request.session[ADMIN_SESSION_KEY] = True


def clear_admin_authenticated(request: Request) -> None:
    if "session" not in request.scope:
        return
    request.session.pop(ADMIN_SESSION_KEY, None)
