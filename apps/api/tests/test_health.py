from fastapi.testclient import TestClient

from casemesh.core.config import get_settings
from casemesh.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "CaseMesh AI"
    assert body["environment"] == "local"
    assert body["version"] == get_settings().app_version
