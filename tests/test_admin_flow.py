from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord


def _clean_db() -> None:
    with SessionLocal() as db:
        db.query(BalanceRecord).delete()
        db.query(ApiKeySource).delete()
        db.commit()


def test_admin_source_management_flow() -> None:
    Base.metadata.create_all(bind=engine)
    _clean_db()
    client = TestClient(app)

    page = client.get("/admin/sources", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/admin/login"

    login = client.post(
        "/admin/login",
        data={"password": "change-me-admin-password"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/admin/sources"

    created = client.post(
        "/admin/sources/new",
        data={
            "name": "admin-source",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "sk-admin-1234567890",
            "key_owner": "admin-owner",
            "remark": "from admin page",
            "interval_seconds": "60",
            "timeout_seconds": "2",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    with SessionLocal() as db:
        source = db.query(ApiKeySource).filter(ApiKeySource.name == "admin-source").first()
        assert source is not None
        source_id = source.id

    edited = client.post(
        f"/admin/sources/{source_id}/edit",
        data={
            "name": "admin-source-updated",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "",
            "key_owner": "admin-owner-2",
            "remark": "updated",
            "interval_seconds": "120",
            "timeout_seconds": "3",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert edited.status_code == 303

    toggled = client.post(f"/admin/sources/{source_id}/toggle", follow_redirects=False)
    assert toggled.status_code == 303

    checked = client.post(f"/admin/sources/{source_id}/check-now", follow_redirects=False)
    assert checked.status_code == 303

    records_page = client.get(f"/admin/sources/{source_id}/records")
    assert records_page.status_code == 200

    with SessionLocal() as db:
        count = db.query(BalanceRecord).filter(BalanceRecord.source_id == source_id).count()
        assert count >= 1

    deleted = client.post(f"/admin/sources/{source_id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
