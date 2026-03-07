from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query_service import build_chart_points, get_source_detail, list_source_dashboard

router = APIRouter(prefix="/ui")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/sources", response_class=HTMLResponse)
async def source_dashboard(
    request: Request,
    key_owner: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = list_source_dashboard(db, key_owner=key_owner)
    return templates.TemplateResponse(
        request=request,
        name="sources_list.html",
        context={"rows": rows, "key_owner": key_owner or ""},
    )


@router.get("/sources/{source_id}", response_class=HTMLResponse)
async def source_detail(
    request: Request,
    source_id: int,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    source, records = get_source_detail(db, source_id, start_at=start_at, end_at=end_at)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")

    chart_points = build_chart_points(records)
    failed_records = [item for item in records if not item.success]
    return templates.TemplateResponse(
        request=request,
        name="source_detail.html",
        context={
            "source": source,
            "records": records,
            "failed_records": failed_records,
            "chart_points": chart_points,
            "start_at": start_at.isoformat() if start_at else "",
            "end_at": end_at.isoformat() if end_at else "",
        },
    )
