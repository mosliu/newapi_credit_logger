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


def test_health_and_ready() -> None:
    Base.metadata.create_all(bind=engine)
    _clean_db()
    client = TestClient(app)

    health = client.get("/api/health")
    ready = client.get("/api/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_source_crud_and_manual_collect() -> None:
    Base.metadata.create_all(bind=engine)
    _clean_db()
    client = TestClient(app)

    payload = {
        "name": "pytest-source",
        "provider_type": "newapi",
        "base_url": "http://127.0.0.1:9",
        "api_key": "sk-pytest-1234567890",
        "key_owner": "pytest-owner",
        "remark": "pytest remark",
        "interval_seconds": 60,
        "timeout_seconds": 2,
        "enabled": True,
    }

    created = client.post("/api/sources", json=payload)
    assert created.status_code == 201
    source_id = created.json()["id"]
    assert created.json()["api_key_masked"].startswith("sk-p")

    collected = client.post(f"/api/scheduler/check-now/{source_id}")
    assert collected.status_code == 200

    listed = client.get("/api/sources")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    with SessionLocal() as db:
        count = db.query(BalanceRecord).filter(BalanceRecord.source_id == source_id).count()
        assert count >= 1

    deleted = client.delete(f"/api/sources/{source_id}")
    assert deleted.status_code == 204
