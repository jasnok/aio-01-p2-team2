from fastapi import APIRouter

from backend.app.mcp_clients.legal_mcp import get_mcp_health


router = APIRouter(tags=["health"])


@router.get("/health", summary="Backend 상태 확인", description="서버가 실행 중인지와 MCP·데이터베이스·Redis의 현재 상태를 확인합니다. mock은 실제 연동 전임을 뜻합니다.")
def health() -> dict:
    try:
        mcp = get_mcp_health()
        mcp_status = mcp.get("status", "unknown")
    except Exception:
        mcp_status = "unavailable"
    return {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
        "is_mock": True,
        "dependencies": {"mcp": "mock" if mcp_status == "unavailable" else mcp_status, "database": "mock", "redis": "disabled"},
    }

