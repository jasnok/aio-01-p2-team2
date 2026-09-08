from app.mcp_clients.mcp_client import call_tool, discover_tools


async def get_mcp_health() -> dict:
    tools = await discover_tools()
    names = [tool["name"] for tool in tools if tool["server"] == "legal"]
    if "search_cases" not in names:
        raise RuntimeError("Legal MCP에 search_cases Tool이 없습니다.")
    return {"status": "ok", "tools": names}


async def search_cases(query: str, category: str, top_k: int = 3) -> dict:
    return await call_tool("legal", "search_cases", {"query": query, "category": category, "top_k": top_k})

