from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import integration_router


client = TestClient(app)


def test_legal_mcp_status_reports_initialization_and_tools(monkeypatch) -> None:
    settings = type("Settings", (), {"legal_mcp_url": "http://legal.test:8013/mcp"})()
    monkeypatch.setattr(integration_router, "get_settings", lambda: settings)

    async def fake_discover_tools():
        return [{"server": "legal", "name": "search_cases"}, {"server": "legal", "name": "get_law_article"}]

    monkeypatch.setattr(integration_router, "discover_tools", fake_discover_tools)
    response = client.get("/api/integration/mcp")
    assert response.status_code == 200
    assert response.json()["initialized"] is True
    assert response.json()["tools"] == ["search_cases", "get_law_article"]



