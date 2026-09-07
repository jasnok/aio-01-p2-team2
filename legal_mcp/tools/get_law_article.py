from legal_mcp.schemas.tools import LawArticleInput, ToolResult


def get_law_article(arguments: LawArticleInput) -> ToolResult:
    """Repository 연결 전 계약 확인용 빈 결과입니다."""
    return ToolResult(success=True, tool="get_law_article", data=None)
