"""Legal MCP Server."""

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from legal_mcp.schemas.tools import (
    LawArticleInput,
    SearchInput,
    SearchLegalDocumentsInput,
)
from legal_mcp.tools.get_case_detail import get_case_detail as get_case_detail_tool
from legal_mcp.tools.get_law_article import get_law_article as get_law_article_tool
from legal_mcp.tools.search_cases import search_cases as search_cases_tool
from legal_mcp.tools.search_legal_documents import (
    search_legal_documents as search_legal_documents_tool,
)

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8011"))

mcp = FastMCP(
    "legal-research-mcp",
    instructions=(
        "법령과 판례를 검색하는 Legal MCP Server입니다. "
        "검색 결과에는 공식 출처 정보를 포함합니다."
    ),
    host=MCP_HOST,
    port=MCP_PORT,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def search_cases(
    query: str,
    category: Literal["housing", "labor", "consumer"],
    top_k: int = 3,
) -> dict:
    """질의와 유사한 판례를 검색합니다."""

    result = search_cases_tool(
        SearchInput(
            query=query,
            category=category,
            top_k=top_k,
        )
    )
    return result.model_dump(mode="json")


@mcp.tool()
def get_case_detail(document_id: int) -> dict:
    """판례 ID로 판례 전문과 상세 정보를 조회합니다."""

    result = get_case_detail_tool(document_id)
    return result.model_dump(mode="json")


@mcp.tool()
def get_law_article(
    law_name: str,
    article_number: str,
) -> dict:
    """법령명과 조문 번호로 특정 조문을 조회합니다."""

    result = get_law_article_tool(
        LawArticleInput(
            law_name=law_name,
            article_number=article_number,
        )
    )
    return result.model_dump(mode="json")


@mcp.tool()
def search_legal_documents(
    query: str,
    category: Literal["housing", "labor", "consumer"],
    document_types: list[Literal["LAW", "CASE"]] = ["LAW", "CASE"],
    top_k: int = 3,
) -> dict:
    """법령과 판례를 통합 검색합니다."""

    result = search_legal_documents_tool(
        SearchLegalDocumentsInput(
            query=query,
            category=category,
            document_types=document_types,
            top_k=top_k,
        )
    )
    return result.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")