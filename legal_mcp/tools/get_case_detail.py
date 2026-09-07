"""판례 상세 정보를 조회하는 Tool."""

from legal_mcp.schemas.tools import Evidence, Source, ToolResult
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()


def get_case_detail(document_id: int) -> ToolResult:
    """판례 ID로 판례 전문과 메타데이터를 조회한다."""

    try:
        row = service.get_case_detail(document_id)

        if row is None:
            return ToolResult(
                success=False,
                tool="get_case_detail",
                data=None,
                error_code="CASE_NOT_FOUND",
                message="해당 판례를 찾을 수 없습니다.",
            )

        item = Evidence(
            evidence_id=f"case-{row['document_id']}",
            document_id=str(row["document_id"]),
            title=row["case_name"] or row["case_number"],
            content=row["content"],
            source=Source(
                source_id=str(row["document_id"]),
                title=row["source_name"] or row["case_name"],
                source_type="case",
                url=row["source_url"] or "",
            ),
            summary=row["summary"],
            case_number=row["case_number"],
            case_name=row["case_name"],
            court=row["court"],
            decided_at=row["decided_at"],
            judgment_result=row["judgment_result"],
        )

        return ToolResult(
            success=True,
            tool="get_case_detail",
            data=item,
        )

    except Exception:
        return ToolResult(
            success=False,
            tool="get_case_detail",
            data=None,
            error_code="CASE_DETAIL_FAILED",
            message="판례 상세 조회 중 오류가 발생했습니다.",
        )