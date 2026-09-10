"""유사 법령 조문을 검색하는 Tool."""

from legal_mcp.schemas.tools import Evidence, SearchInput, Source, ToolResult
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def search_laws(arguments: SearchInput) -> ToolResult:
    """질의와 유사한 법령 조문을 벡터 검색한다."""

    try:
        rows = service.search_laws(
            query=arguments.query,
            category=arguments.category,
            top_k=arguments.top_k,
        )

        items = [
            Evidence(
                evidence_id=f"law-{row['document_id']}",
                document_id=str(row["document_id"]),
                title=(
                    row["title"]
                    or f"{row['law_name']} {row['article_number']}"
                ),
                content=row["chunk_content"],
                source=Source(
                    source_id=str(row["document_id"]),
                    title=row["source_name"] or row["law_name"],
                    source_type="law",
                    url=row["source_url"] or "",
                ),
                score=float(row["similarity"]),
                law_name=row["law_name"],
                article_number=row["article_number"],
                metadata={
                    "category": arguments.category,
                    "retrieval_method": "hybrid",
                    "effective_date": (
                        row["effective_date"].isoformat()
                        if row["effective_date"]
                        else None
                    ),
                },
            )
            for row in rows
        ]

        return ToolResult(
            success=True,
            tool="search_laws",
            data=items,
        )

    except Exception:
        return ToolResult(
            success=False,
            tool="search_laws",
            data=None,
            error_code="SEARCH_LAWS_FAILED",
            message="법령 검색 중 오류가 발생했습니다.",
        )