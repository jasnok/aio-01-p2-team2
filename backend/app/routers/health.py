from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.mcp_clients.legal_mcp import get_mcp_health


router = APIRouter(tags=["health"])


async def _database_status() -> str:
    """Check the database directly so Docker health does not depend on MCP discovery."""
    try:
        import asyncpg

        connection = await asyncpg.connect(get_settings().database_url, timeout=3)
        try:
            await connection.execute("SELECT 1")
        finally:
            await connection.close()
        return "ok"
    except Exception:
        return "unavailable"


async def _redis_status() -> str:
    settings = get_settings()
    if not settings.redis_enabled:
        return "disabled"
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return "ok"
    except Exception:
        return "unavailable"


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
    database_status = await _database_status()
    redis_status = await _redis_status()
    return {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
        "is_mock": False,
        "dependencies": {"mcp": mcp_status, "database": database_status, "redis": redis_status},
    }

