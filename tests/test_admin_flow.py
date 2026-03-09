from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.api_key_source import ApiKeySource
from app.models.balance_record import BalanceRecord


def _reset_db_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_admin_source_management_flow() -> None:
    _reset_db_schema()
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

    create_form = client.get("/admin/sources/new")
    assert create_form.status_code == 200
    assert 'name="api_key"' in create_form.text
    assert 'name="api_key" value="" required' in create_form.text

    created_without_key = client.post(
        "/admin/sources/new",
        data={
            "name": "admin-source-invalid",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "",
            "key_owner": "admin-owner",
            "interval_seconds": "60",
            "timeout_seconds": "2",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert created_without_key.status_code == 400
    assert "api_key 为必填项" in created_without_key.text

    created = client.post(
        "/admin/sources/new",
        data={
            "name": "admin-source",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "sk-admin-1234567890",
            "key_owner": "admin-owner",
            "key_account": "owner-account-1",
            "customer_info": "first-customer",
            "key_created_at": "2026-02-01T10:20",
            "fee_amount": "88.80",
            "fee_currency": "CNY",
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
        assert source.key_account == "owner-account-1"
        assert source.customer_info == "first-customer"
        assert source.key_created_at is not None
        assert str(source.fee_amount) in {"88.8", "88.80"}
        assert source.fee_currency == "CNY"

    sources_page = client.get("/admin/sources")
    assert sources_page.status_code == 200
    assert f"/admin/sources/new?copy_from={source_id}" in sources_page.text

    copied_form = client.get(f"/admin/sources/new?copy_from={source_id}")
    assert copied_form.status_code == 200
    assert 'value="admin-source-copy"' in copied_form.text
    assert 'value="owner-account-1"' in copied_form.text
    assert 'value="" required' in copied_form.text
    assert "来源监控源 ID" in copied_form.text

    copied_created = client.post(
        "/admin/sources/new",
        data={
            "name": "admin-source-copy-created",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "sk-admin-copy-1234567890",
            "key_owner": "admin-owner",
            "key_account": "owner-account-1",
            "customer_info": "first-customer",
            "key_created_at": "2026-02-01T10:20",
            "fee_amount": "88.80",
            "fee_currency": "CNY",
            "remark": "copied and created",
            "interval_seconds": "60",
            "timeout_seconds": "2",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert copied_created.status_code == 303

    edited = client.post(
        f"/admin/sources/{source_id}/edit",
        data={
            "name": "admin-source-updated",
            "provider_type": "newapi",
            "base_url": "http://127.0.0.1:9",
            "api_key": "",
            "key_owner": "admin-owner-2",
            "key_account": "owner-account-2",
            "customer_info": "updated-customer",
            "key_created_at": "2026-02-02T11:30",
            "fee_amount": "99.90",
            "fee_currency": "USD",
            "remark": "updated",
            "interval_seconds": "120",
            "timeout_seconds": "3",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert edited.status_code == 303

    with SessionLocal() as db:
        updated = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
        assert updated is not None
        assert updated.key_account == "owner-account-2"
        assert updated.customer_info == "updated-customer"
        assert updated.key_created_at is not None
        assert updated.key_created_at.strftime("%Y-%m-%d %H:%M") == "2026-02-02 11:30"
        assert str(updated.fee_amount) in {"99.9", "99.90"}
        assert updated.fee_currency == "USD"

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
