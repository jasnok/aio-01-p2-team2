"""공식 상담·해석 사례를 검색하는 Tool."""

from legal_mcp.schemas.tools import Evidence, SearchInput, Source, ToolResult
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def search_consultations(arguments: SearchInput) -> ToolResult:
    """질의와 유사한 공식 상담·해석 사례를 Hybrid Search한다."""

    try:
        rows = service.search_consultations(
            query=arguments.query,
            category=arguments.category,
            top_k=arguments.top_k,
        )

        items = [
            Evidence(
                evidence_id=f"consultation-{row['document_id']}",
                document_id=str(row["document_id"]),
                title=row["title"],
                content=row["chunk_content"],
                source=Source(
                    source_id=str(row["document_id"]),
                    title=row["source_name"],
                    source_type="consultation",
                    url=row["source_url"] or "",
                ),
                score=float(row["similarity"]),
                summary=row["summary"],
                metadata={
                    "category": arguments.category,
                    "document_type": "CONSULTATION",
                    "retrieval_method": "hybrid",
                },
            )
            for row in rows
        ]

        return ToolResult(
            success=True,
            tool="search_consultations",
            data=items,
        )

    except Exception:
        return ToolResult(
            success=False,
            tool="search_consultations",
            data=None,
            error_code="SEARCH_CONSULTATIONS_FAILED",
            message="상담 사례 검색 중 오류가 발생했습니다.",
        )