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
        "dependencies": {"mcp": mcp_status, "database": "mock", "redis": "disabled"},
    }

