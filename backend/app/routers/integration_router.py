import asyncio
import uuid

from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.mcp_clients.mcp_client import call_tool, discover_tools
from backend.app.schemas.integration import FoodSearchRequest, FoodSearchResponse, McpStatusResponse


router = APIRouter(prefix="/api/integration", tags=["integration-smoke-test"])


def _ensure_enabled() -> None:
    if not get_settings().enable_integration_debug:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "INTEGRATION_DEBUG_DISABLED",
                "message": "통합 확인 기능이 비활성화되어 있습니다.",
            },
        )


def _mcp_error(error: Exception) -> HTTPException:
    code = "MCP_TIMEOUT" if isinstance(error, (TimeoutError, asyncio.TimeoutError)) else "MCP_UNAVAILABLE"
    return HTTPException(
        status_code=503,
        detail={"code": code, "message": str(error) or "Food MCP 연결에 실패했습니다."},
    )


@router.get("/mcp", response_model=McpStatusResponse)
async def get_mcp_status() -> McpStatusResponse:
    _ensure_enabled()
    try:
        tools = await discover_tools()
    except Exception as error:
        raise _mcp_error(error) from error
    settings = get_settings()
    return McpStatusResponse(
        server="food",
        url=settings.food_mcp_url,
        tools=[tool["name"] for tool in tools if tool["server"] == "food"],
    )


@router.post("/mcp/food-search", response_model=FoodSearchResponse)
async def search_food(request: FoodSearchRequest) -> FoodSearchResponse:
    _ensure_enabled()
    try:
        payload = await call_tool("food", "search_restaurants", request.model_dump())
    except Exception as error:
        raise _mcp_error(error) from error
    return FoodSearchResponse(
        request_id=f"smoke-{uuid.uuid4()}",
        path=["frontend", "backend", "food_mcp"],
        server="food",
        tool="search_restaurants",
        items=payload.get("items", []),
        count=payload.get("count", 0),
        source=payload.get("source", "unknown"),
        allergy_notice=payload.get("allergy_notice", ""),
    )

