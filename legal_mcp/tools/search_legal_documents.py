"""법령과 판례를 통합 검색하는 Tool."""

from legal_mcp.schemas.tools import (
    Evidence,
    SearchLegalDocumentsInput,
    Source,
    ToolResponse,
)
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def search_legal_documents(
    arguments: SearchLegalDocumentsInput,
) -> ToolResponse:
    """질의와 관련된 법령 및 판례를 통합 검색한다."""

    try:
        rows = service.search_legal_documents(
            query=arguments.query,
            category=arguments.category,
            document_types=arguments.document_types,
            top_k=arguments.top_k,
        )

        items = []

        for row in rows:
            is_case = row["document_type"] == "CASE"

            item = Evidence(
                evidence_id=f"{row['document_type'].lower()}-{row['document_id']}",
                document_id=str(row["document_id"]),
                title=(
                    row["case_name"]
                    if is_case
                    else row["title"]
                    or f"{row['law_name']} {row['article_number']}"
                ),
                content=row["chunk_content"],
                source=Source(
                    source_id=str(row["document_id"]),
                    title=(
                        row["source_name"]
                        or row["case_name"]
                        if is_case
                        else row["source_name"] or row["law_name"]
                    ),
                    source_type="case" if is_case else "law",
                    url=row["source_url"] or "",
                ),
                score=float(row["similarity"]),
                summary=row["summary"] if is_case else None,
                law_name=None if is_case else row["law_name"],
                article_number=None if is_case else row["article_number"],
                case_number=row["case_number"] if is_case else None,
                case_name=row["case_name"] if is_case else None,
                court=row["court"] if is_case else None,
                decided_at=row["decided_at"] if is_case else None,
                judgment_result=row["judgment_result"] if is_case else None,
                metadata={
                    "document_type": row["document_type"],
                    "category": arguments.category,
                },
            )
            items.append(item)

        return ToolResponse(
            success=True,
            data={"items": items},
            meta={
                "query": arguments.query,
                "category": arguments.category,
                "document_types": arguments.document_types,
                "result_count": len(items),
                "retrieval_method": "vector",
            },
            error=None,
        )

    except Exception:
        return ToolResponse(
            success=False,
            data=None,
            meta={},
            error={
                "code": "SEARCH_LEGAL_DOCUMENTS_FAILED",
                "message": "법령·판례 통합 검색 중 오류가 발생했습니다.",
            },
        )