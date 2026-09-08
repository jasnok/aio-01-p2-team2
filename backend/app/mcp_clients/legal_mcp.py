from backend.app.mcp_clients.mcp_client import call_tool, discover_tools


async def get_mcp_health() -> dict:
    tools = await discover_tools()
    names = [tool["name"] for tool in tools if tool["server"] == "legal"]
    if "search_cases" not in names:
        raise RuntimeError("Legal MCP에 search_cases Tool이 없습니다.")
    return {"status": "ok", "tools": names}


async def search_cases(query: str, category: str, top_k: int = 3) -> dict:
    return await call_tool("legal", "search_cases", {"query": query, "category": category, "top_k": top_k})


async def search_consultations(query: str, category: str, top_k: int = 3) -> dict:
    """소비자원 등 상담·해석 사례를 Legal MCP에서 검색한다."""
    return await call_tool(
        "legal",
        "search_consultations",
        {"query": query, "category": category, "top_k": top_k},
    )


async def search_legal_documents(
        query: str,
        category: str,
        document_types: list[str] | None = None,
        top_k: int = 3,
    ) -> dict:
    arguments = {
        "query": query,
        "category": category,
        "document_types": document_types or ["LAW", "CASE"],
        "top_k": top_k,
    }

    return await call_tool(
        "legal",
        "search_legal_documents",
        arguments,
    )

async def search_laws(
    query: str,
    category: str,
    top_k: int = 3,
) -> dict:
    return await call_tool(
        "legal",
        "search_laws",
        {
            "query": query,
            "category": category,
            "top_k": top_k,
        },
    )


async def get_case_detail(document_id: int) -> dict:
    return await call_tool(
        "legal",
        "get_case_detail",
        {
            "document_id": document_id,
        },
    )


async def get_law_article(
    law_name: str,
    article_number: str,
) -> dict:
    return await call_tool(
        "legal",
        "get_law_article",
        {
            "law_name": law_name,
            "article_number": article_number,
        },
    )