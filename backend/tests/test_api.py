from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import legal_question_service


client = TestClient(app)


def test_health_returns_backend_status() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_legal_question_uses_public_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        legal_question_service,
        "search_legal_documents",
        lambda *args, **kwargs: {"success": True, "data": {"items": []}},
    )
    response = client.post(
        "/api/legal/questions",
        json={
            "session_id": "web-test",
            "category": "labor",
            "question": "퇴직금을 받지 못했습니다.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "labor"
    assert payload["related_laws"] == []
    assert payload["similar_cases"] == []
