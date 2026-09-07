"""유사 판례를 검색하는 Tool."""

from legal_mcp.schemas.tools import Evidence, SearchInput, Source, ToolResult
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def search_cases(arguments: SearchInput) -> ToolResult:
    """질의와 유사한 판례를 벡터 검색한다."""

    try:
        rows = service.search_cases(
            query=arguments.query,
            category=arguments.category,
            top_k=arguments.top_k,
        )

        items = [
            Evidence(
                evidence_id=f"case-{row['document_id']}",
                document_id=str(row["document_id"]),
                title=row["case_name"] or row["case_number"],
                content=row["chunk_content"],
                source=Source(
                    source_id=str(row["document_id"]),
                    title=row["source_name"] or row["case_name"],
                    source_type="case",
                    url=row["source_url"] or "",
                ),
                score=float(row["similarity"]),
                summary=row["summary"],
                case_number=row["case_number"],
                case_name=row["case_name"],
                court=row["court"],
                decided_at=row["decided_at"],
                judgment_result=row["judgment_result"],
                metadata={
                    "category": arguments.category,
                    "retrieval_method": "vector",
                },
            )
            for row in rows
        ]

        return ToolResult(
            success=True,
            tool="search_cases",
            data=items,
        )

    except Exception:
        return ToolResult(
            success=False,
            tool="search_cases",
            data=None,
            error_code="SEARCH_CASES_FAILED",
            message="판례 검색 중 오류가 발생했습니다.",
        )