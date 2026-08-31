from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import integration_router


client = TestClient(app)


def test_integration_route_is_hidden_when_disabled(monkeypatch) -> None:
    settings = type("Settings", (), {"enable_integration_debug": False})()
    monkeypatch.setattr(integration_router, "get_settings", lambda: settings)
    response = client.get("/api/integration/mcp")
    assert response.status_code == 404


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

