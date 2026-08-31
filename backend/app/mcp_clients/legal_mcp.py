import httpx

from app.core.config import get_settings


def get_mcp_health() -> dict:
    settings = get_settings()
    response = httpx.get(f"{settings.mcp_server_url.rstrip('/')}/health", timeout=5)
    response.raise_for_status()
    return response.json()


def search_legal_documents(query: str, category: str, top_k: int = 3) -> dict:
    settings = get_settings()
    response = httpx.post(
        f"{settings.mcp_server_url.rstrip('/')}/tools/search_legal_documents",
        json={"query": query, "category": category, "document_types": ["LAW", "CASE"], "top_k": top_k},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()

