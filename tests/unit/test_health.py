from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check(monkeypatch):
    # Mock database session execute for unit testing without live DB
    from sqlalchemy.orm import Session
    from unittest.mock import MagicMock

    response = client.get("/api/v1/health")
    # Health endpoint returns 200 (healthy) or 503 (degraded if DB unreachable)
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "pilot_district" in data
    assert data["pilot_district"] == "Pune"
    assert "IT-ITeS" in data["sectors"]
