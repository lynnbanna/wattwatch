from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_health_ok_when_database_reachable(monkeypatch):
    monkeypatch.setattr(db, "check_database", lambda: True)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0.1.0", "database": "ok"}


def test_health_degraded_when_database_down(monkeypatch):
    monkeypatch.setattr(db, "check_database", lambda: False)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


def test_responses_carry_request_id(monkeypatch):
    monkeypatch.setattr(db, "check_database", lambda: True)
    res = client.get("/api/v1/health", headers={"x-request-id": "abc123"})
    assert res.headers["x-request-id"] == "abc123"
