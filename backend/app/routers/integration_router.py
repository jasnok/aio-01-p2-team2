import asyncio

from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.mcp_clients.mcp_client import discover_tools
from backend.app.schemas.integration import McpStatusResponse


router = APIRouter(prefix="/api/integration", tags=["integration-smoke-test"])


def _mcp_error(error: Exception) -> HTTPException:
    code = "MCP_TIMEOUT" if isinstance(error, (TimeoutError, asyncio.TimeoutError)) else "MCP_UNAVAILABLE"
    return HTTPException(
        status_code=503,
        detail={"code": code, "message": "Legal MCP 연결 또는 초기화에 실패했습니다."},
    )


@router.get("/mcp", response_model=McpStatusResponse)
async def get_mcp_status() -> McpStatusResponse:
    try:
        tools = await discover_tools()
    except Exception as error:
        raise _mcp_error(error) from error
    settings = get_settings()
    legal_tools = [tool["name"] for tool in tools if tool["server"] == "legal"]
    return McpStatusResponse(
        server="legal",
        url=settings.legal_mcp_url,
        initialized=True,
        tools=legal_tools,
        tool_count=len(legal_tools),
    )



