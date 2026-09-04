from legal_mcp.schemas.tools import SearchInput, ToolResult


def search_cases(arguments: SearchInput) -> ToolResult:
    """Repository 연결 전 계약 확인용 빈 결과입니다."""
    return ToolResult(success=True, tool="search_cases", data=[])
