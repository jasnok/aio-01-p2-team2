from fastapi import APIRouter

from app.core.config import get_settings
from app.mcp_clients.legal_mcp import get_mcp_health


router = APIRouter(tags=["health"])


@router.get("/health", summary="Backend 상태 확인", description="서버가 실행 중인지와 MCP·데이터베이스·Redis의 현재 상태를 확인합니다. mock은 실제 연동 전임을 뜻합니다.")
async def health() -> dict:
    if get_settings().backend_mock_mode:
        return {
            "status": "ok", "service": "backend", "version": "0.1.0", "is_mock": True,
            "dependencies": {"mcp": "mock", "database": "mock", "redis": "disabled"},
        }
    try:
        mcp = await get_mcp_health()
        mcp_status = mcp.get("status", "unknown")
    except Exception:
        mcp_status = "unavailable"
    return {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
        "is_mock": False,
        "dependencies": {"mcp": mcp_status, "database": "ok" if mcp_status == "ok" else "unavailable", "redis": "disabled"},
    }

