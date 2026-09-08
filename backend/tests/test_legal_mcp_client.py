import asyncio

from backend.app.mcp_clients import legal_mcp


def test_search_legal_documents_uses_default_document_types(monkeypatch) -> None:
    received = {}

    async def fake_call_tool(
            server_name: str,
            tool_name: str,
            arguments: dict,
    ) -> dict:
        received["sever_name"] = server_name
        received["tool_name"] = tool_name
        received["arguments"] = arguments

        return {
            "success": True,
            "data": {
                "items": [],
            },
        }

    monkeypatch.setattr(
        legal_mcp,
        "call_tool",
        fake_call_tool,
    )

    result = asyncio.run(
        legal_mcp.search_legal_documents(
            query="퇴직금 관련 법률과 판례를 찾고 싶습니다.",
            category="labor",
        )
    )

    assert received["sever_name"] == "legal"
    assert received["tool_name"] == "search_legal_documents"
    assert received["arguments"]["query"] == "퇴직금 관련 법률과 판례를 찾고 싶습니다."
    assert received["arguments"]["category"] == "labor"
    assert received["arguments"]["document_types"] == ["LAW", "CASE"]
    assert received["arguments"]["top_k"] == 3
    assert result["success"] is True