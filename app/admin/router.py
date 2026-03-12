from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.source import SourceCreate, SourceUpdate
from app.core.config import get_settings
from app.db.session import get_db
from app.services.admin_auth_service import (
    clear_admin_authenticated,
    is_admin_authenticated,
    mark_admin_authenticated,
    verify_admin_password,
)
from app.services.providers.catalog import get_provider_options
from app.services.query_service import (
    build_chart_points,
    get_source_detail,
    list_source_balance_changes,
    list_source_dashboard,
)
from app.services.source_service import create_source, delete_source, get_source, update_source
from app.tasks.scheduler_service import source_scheduler_service

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["app_version"] = get_settings().app_version

_ADMIN_TOAST_SESSION_KEY = "admin_toast"


def _as_optional(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    return stripped if stripped else None


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", []))
        msg = error.get("msg", "invalid value")
        parts.append(f"{loc}: {msg}")
    return "; ".join(parts)


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)

def _set_toast(request: Request, message: str) -> None:
    if "session" not in request.scope:
        return
    request.session[_ADMIN_TOAST_SESSION_KEY] = message


def _pop_toast(request: Request) -> str | None:
    if "session" not in request.scope:
        return None
    value = request.session.pop(_ADMIN_TOAST_SESSION_KEY, None)
    if value is None:
        return None
    return str(value)


def _render_form(
    request: Request,
    *,
    form_data: dict,
    action_url: str,
    title: str,
    error: str | None = None,
    api_key_required: bool = False,
    copied_from_source_id: int | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="source_form.html",
        context={
            "title": title,
            "action_url": action_url,
            "error": error,
            "form_data": form_data,
            "provider_options": get_provider_options(),
            "api_key_required": api_key_required,
            "copied_from_source_id": copied_from_source_id,
            "is_admin_authenticated": is_admin_authenticated(request),
        },
        status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK,
    )


def _render_login_form(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "后台登录",
            "error": error,
            "is_admin_authenticated": is_admin_authenticated(request),
        },
        status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK,
    )


def _default_form_data() -> dict:
    return {
        "name": "",
        "provider_type": "newapi",
        "base_url": "",
        "api_key": "",
        "key_owner": "",
        "key_account": "",
        "customer_info": "",
        "key_created_at": "",
        "fee_amount": "",
        "fee_currency": "",
        "remark": "",
        "interval_seconds": str(get_settings().default_poll_interval_seconds),
        "timeout_seconds": "20",
        "enabled": True,
    }


@router.get("/login", response_class=HTMLResponse)
async def admin_login_form(request: Request) -> Response:
    if is_admin_authenticated(request):
        return _redirect("/admin/sources")
    return _render_login_form(request)


@router.post("/login", response_class=HTMLResponse)
async def admin_login(request: Request) -> Response:
    form = await request.form()
    password = str(form.get("password", ""))
    if not verify_admin_password(password):
        return _render_login_form(request, error="登录密码错误")

    mark_admin_authenticated(request)
    return _redirect("/admin/sources")


@router.post("/logout")
async def admin_logout(request: Request) -> RedirectResponse:
    clear_admin_authenticated(request)
    return _redirect("/admin/login")


@router.get("", response_class=HTMLResponse)
async def admin_root() -> RedirectResponse:
    return _redirect("/admin/sources")


@router.get("/sources", response_class=HTMLResponse)
async def admin_sources(
    request: Request,
    key_owner: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = list_source_dashboard(db, key_owner=key_owner)
    toast = _pop_toast(request)
    return templates.TemplateResponse(
        request=request,
        name="sources_list.html",
        context={
            "rows": rows,
            "key_owner": key_owner or "",
            "toast": toast or "",
            "is_admin_authenticated": is_admin_authenticated(request),
        },
    )


@router.get("/sources/analyze", response_class=HTMLResponse)
async def admin_sources_analyze(
    request: Request,
    minutes: int = Query(default=30, ge=1, le=1440),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    window_end = datetime.utcnow()
    window_start = window_end - timedelta(minutes=minutes)
    rows = list_source_balance_changes(db, window_start=window_start, window_end=window_end)
    return templates.TemplateResponse(
        request=request,
        name="source_analyze.html",
        context={
            "rows": rows,
            "minutes": minutes,
            "range_start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
            "range_end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
            "is_admin_authenticated": is_admin_authenticated(request),
        },
    )


@router.get("/sources/new", response_class=HTMLResponse)
async def admin_source_create_form(
    request: Request,
    copy_from: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    form_data = _default_form_data()
    copied_from_source_id: int | None = None
    if copy_from is not None:
        source = get_source(db, copy_from)
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
        form_data.update(
            {
                "name": f"{source.name}-copy",
                "provider_type": source.provider_type,
                "base_url": source.base_url,
                "key_owner": source.key_owner,
                "key_account": source.key_account or "",
                "customer_info": source.customer_info or "",
                "key_created_at": (
                    source.key_created_at.strftime("%Y-%m-%dT%H:%M") if source.key_created_at else ""
                ),
                "fee_amount": str(source.fee_amount) if source.fee_amount is not None else "",
                "fee_currency": source.fee_currency or "",
                "remark": source.remark or "",
                "interval_seconds": str(source.interval_seconds),
                "timeout_seconds": str(source.timeout_seconds),
                "enabled": source.enabled,
            }
        )
        copied_from_source_id = source.id

    return _render_form(
        request,
        form_data=form_data,
        action_url="/admin/sources/new",
        title="新增监控源",
        api_key_required=True,
        copied_from_source_id=copied_from_source_id,
    )


@router.post("/sources/new", response_class=HTMLResponse)
async def admin_source_create(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    raw_api_key = str(form.get("api_key", "")).strip()
    raw_payload = {
        "name": str(form.get("name", "")),
        "provider_type": str(form.get("provider_type", "newapi")),
        "base_url": str(form.get("base_url", "")),
        "api_key": raw_api_key,
        "key_owner": str(form.get("key_owner", "")),
        "key_account": _as_optional(str(form.get("key_account", ""))),
        "customer_info": _as_optional(str(form.get("customer_info", ""))),
        "key_created_at": _as_optional(str(form.get("key_created_at", ""))),
        "fee_amount": _as_optional(str(form.get("fee_amount", ""))),
        "fee_currency": _as_optional(str(form.get("fee_currency", ""))),
        "remark": _as_optional(str(form.get("remark", ""))),
        "interval_seconds": str(
            form.get("interval_seconds", str(get_settings().default_poll_interval_seconds))
        ),
        "timeout_seconds": str(form.get("timeout_seconds", "20")),
        "enabled": bool(form.get("enabled")),
    }

    if not raw_api_key:
        return _render_form(
            request,
            form_data=raw_payload,
            action_url="/admin/sources/new",
            title="新增监控源",
            error="api_key 为必填项。",
            api_key_required=True,
        )

    try:
        payload = SourceCreate.model_validate(raw_payload)
        create_source(db, payload)
    except ValidationError as exc:
        return _render_form(
            request,
            form_data=raw_payload,
            action_url="/admin/sources/new",
            title="新增监控源",
            error=_validation_message(exc),
            api_key_required=True,
        )
    except IntegrityError:
        db.rollback()
        return _render_form(
            request,
            form_data=raw_payload,
            action_url="/admin/sources/new",
            title="新增监控源",
            error="名称已存在，请使用其他名称。",
            api_key_required=True,
        )

    source_scheduler_service.reload_jobs()
    return _redirect("/admin/sources")


@router.get("/sources/{source_id}/edit", response_class=HTMLResponse)
async def admin_source_edit_form(
    source_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    source = get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    return _render_form(
        request,
        form_data={
            "name": source.name,
            "provider_type": source.provider_type,
            "base_url": source.base_url,
            "api_key": "",
            "key_owner": source.key_owner,
            "key_account": source.key_account or "",
            "customer_info": source.customer_info or "",
            "key_created_at": (
                source.key_created_at.strftime("%Y-%m-%dT%H:%M") if source.key_created_at else ""
            ),
            "fee_amount": str(source.fee_amount) if source.fee_amount is not None else "",
            "fee_currency": source.fee_currency or "",
            "remark": source.remark or "",
            "interval_seconds": str(source.interval_seconds),
            "timeout_seconds": str(source.timeout_seconds),
            "enabled": source.enabled,
        },
        action_url=f"/admin/sources/{source_id}/edit",
        title=f"编辑监控源 #{source_id}",
        api_key_required=False,
    )


@router.post("/sources/{source_id}/edit", response_class=HTMLResponse)
async def admin_source_edit(source_id: int, request: Request, db: Session = Depends(get_db)):
    existing = get_source(db, source_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    form = await request.form()
    raw_payload = {
        "name": str(form.get("name", "")),
        "provider_type": str(form.get("provider_type", "newapi")),
        "base_url": str(form.get("base_url", "")),
        "api_key": _as_optional(str(form.get("api_key", ""))),
        "key_owner": str(form.get("key_owner", "")),
        "key_account": _as_optional(str(form.get("key_account", ""))),
        "customer_info": _as_optional(str(form.get("customer_info", ""))),
        "key_created_at": _as_optional(str(form.get("key_created_at", ""))),
        "fee_amount": _as_optional(str(form.get("fee_amount", ""))),
        "fee_currency": _as_optional(str(form.get("fee_currency", ""))),
        "remark": _as_optional(str(form.get("remark", ""))),
        "interval_seconds": str(
            form.get("interval_seconds", str(get_settings().default_poll_interval_seconds))
        ),
        "timeout_seconds": str(form.get("timeout_seconds", "20")),
        "enabled": bool(form.get("enabled")),
    }

    try:
        payload = SourceUpdate.model_validate(raw_payload)
        result = update_source(db, source_id, payload)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    except ValidationError as exc:
        return _render_form(
            request,
            form_data=raw_payload,
            action_url=f"/admin/sources/{source_id}/edit",
            title=f"编辑监控源 #{source_id}",
            error=_validation_message(exc),
            api_key_required=False,
        )
    except IntegrityError:
        db.rollback()
        return _render_form(
            request,
            form_data=raw_payload,
            action_url=f"/admin/sources/{source_id}/edit",
            title=f"编辑监控源 #{source_id}",
            error="名称已存在，请使用其他名称。",
            api_key_required=False,
        )

    source_scheduler_service.reload_jobs()
    return _redirect("/admin/sources")


@router.post("/sources/{source_id}/toggle")
async def admin_source_toggle(source_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    source = get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    payload = SourceUpdate(enabled=not source.enabled)
    update_source(db, source_id, payload)
    source_scheduler_service.reload_jobs()
    return _redirect("/admin/sources")


@router.post("/sources/{source_id}/check-now")
async def admin_source_check_now(request: Request, source_id: int) -> RedirectResponse:
    return_to = "/admin/sources"
    try:
        form = await request.form()
        candidate = str(form.get("return_to", "")).strip()
        if candidate.startswith("/admin/sources"):
            return_to = candidate
    except Exception:  # noqa: BLE001
        pass

    try:
        ok = source_scheduler_service.collect_now(source_id)
    except Exception:  # noqa: BLE001
        _set_toast(request, "采集失败：请查看日志排障")
        return _redirect(return_to)

    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    _set_toast(request, "采集完成：已写入最新记录")
    return _redirect(return_to)


@router.post("/sources/{source_id}/delete")
async def admin_source_delete(source_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    deleted = delete_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    source_scheduler_service.reload_jobs()
    return _redirect("/admin/sources")


@router.get("/sources/{source_id}/records", response_class=HTMLResponse)
async def admin_source_records(
    request: Request,
    source_id: int,
    start_day: date | None = Query(default=None, alias="start_date"),
    end_day: date | None = Query(default=None, alias="end_date"),
    day: date | None = Query(default=None, alias="date"),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    filter_message: str | None = None
    if start_at is None and end_at is None:
        if start_day is None and end_day is None:
            selected_start = day or datetime.now().date()
            selected_end = selected_start
        else:
            selected_start = start_day or end_day or datetime.now().date()
            selected_end = end_day or start_day or selected_start

        if selected_end < selected_start:
            filter_message = "结束日期早于起始日期，已自动交换。"
            selected_start, selected_end = selected_end, selected_start

        start_at = datetime.combine(selected_start, time.min)
        end_at = datetime.combine(selected_end, time.min) + timedelta(days=1)
        start_day = selected_start
        end_day = selected_end
    else:
        start_day = start_at.date() if start_at else (end_at.date() if end_at else start_day)
        end_day = end_at.date() if end_at else start_day

    source, records = get_source_detail(db, source_id, start_at=start_at, end_at=end_at)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    chart_points = build_chart_points(records)
    failed_records = [item for item in records if not item.success]
    return templates.TemplateResponse(
        request=request,
        name="source_records.html",
        context={
            "source": source,
            "records": records,
            "failed_records": failed_records,
            "chart_points": chart_points,
            "filter_start_date": start_day.isoformat() if start_day else "",
            "filter_end_date": end_day.isoformat() if end_day else "",
            "range_start": start_at.strftime("%Y-%m-%d %H:%M:%S") if start_at else "",
            "range_end": end_at.strftime("%Y-%m-%d %H:%M:%S") if end_at else "",
            "filter_message": filter_message or "",
            "is_admin_authenticated": is_admin_authenticated(request),
        },
    )
