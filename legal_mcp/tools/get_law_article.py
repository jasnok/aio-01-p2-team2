"""법령 조문 상세 정보를 조회하는 Tool."""

from legal_mcp.schemas.tools import Evidence, LawArticleInput, Source, ToolResult
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def get_law_article(arguments: LawArticleInput) -> ToolResult:
    """법령명과 조문 번호로 조문 전문을 조회한다."""

    try:
        row = service.get_law_article(
            law_name=arguments.law_name,
            article_number=arguments.article_number,
        )

        if row is None:
            return ToolResult(
                success=False,
                tool="get_law_article",
                data=None,
                error_code="LAW_NOT_FOUND",
                message="해당 법령 또는 조문을 찾을 수 없습니다.",
            )

        item = Evidence(
            evidence_id=f"law-{row['document_id']}",
            document_id=str(row["document_id"]),
            title=row["title"] or f"{row['law_name']} {row['article_number']}",
            content=row["content"],
            source=Source(
                source_id=str(row["document_id"]),
                title=row["source_name"] or row["law_name"],
                source_type="law",
                url=row["source_url"] or "",
            ),
            summary=None,
            law_name=row["law_name"],
            article_number=row["article_number"],
            metadata={
                "effective_date": (
                    row["effective_date"].isoformat()
                    if row["effective_date"]
                    else None
                ),
            },
        )

        return ToolResult(
            success=True,
            tool="get_law_article",
            data=item,
        )

    except Exception:
        return ToolResult(
            success=False,
            tool="get_law_article",
            data=None,
            error_code="LAW_ARTICLE_FAILED",
            message="법령 조문 조회 중 오류가 발생했습니다.",
        )