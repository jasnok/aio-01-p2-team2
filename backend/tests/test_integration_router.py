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


def test_food_search_returns_mcp_payload(monkeypatch) -> None:
    settings = type(
        "Settings",
        (),
        {"enable_integration_debug": True, "food_mcp_url": "http://mcp.test/mcp"},
    )()
    monkeypatch.setattr(integration_router, "get_settings", lambda: settings)

    async def fake_call_tool(server_name, tool_name, arguments):
        return {
            "items": [
                {
                    "restaurant_id": "rest-test-001",
                    "name": "테스트식당",
                    "region": "서울",
                    "food_category": "한식",
                    "price": 10000,
                    "allergy": [],
                }
            ],
            "count": 1,
            "source": "food-restaurant-catalog",
        }

    monkeypatch.setattr(integration_router, "call_tool", fake_call_tool)
    response = client.post(
        "/api/integration/mcp/food-search",
        json={
            "region": "서울",
            "food_category": "한식",
            "max_price": 20000,
            "allergy": "없음",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    assert response.json()["path"] == ["frontend", "backend", "food_mcp"]
    assert response.json()["items"][0]["name"] == "테스트식당"

