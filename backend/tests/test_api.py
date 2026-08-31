from starlette.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_returns_backend_status() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

