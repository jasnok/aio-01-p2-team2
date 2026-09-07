from fastapi import APIRouter

from backend.app.mcp_clients.legal_mcp import get_mcp_health


router = APIRouter(tags=["health"])


@router.get("/health")
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

