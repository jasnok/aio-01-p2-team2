import uuid

from app.mcp_clients.legal_mcp import search_legal_documents
from app.schemas.legal import LegalDocument, LegalQuestionRequest, LegalQuestionResponse


DISCLAIMER = "이 결과는 서버 연결 확인용 Mock이며 법률 자문이나 실제 법률 정보가 아닙니다."


def answer_question(request: LegalQuestionRequest) -> LegalQuestionResponse:
    tool_result = search_legal_documents(request.message, request.category)
    if not tool_result.get("success"):
        raise RuntimeError(tool_result.get("error", {}).get("message", "MCP Tool 실행 실패"))

    documents = [LegalDocument.model_validate(item) for item in tool_result["data"]["items"]]
    laws = [item for item in documents if item.document_type == "LAW"]
    cases = [item for item in documents if item.document_type == "CASE"]
    titles = ", ".join(item.title for item in documents)

    return LegalQuestionResponse(
        request_id=f"req-{uuid.uuid4()}",
        category=request.category,
        question_summary=f"{request.category} 카테고리 Mock 검색",
        answer=f"서버 연결에 성공했습니다. Mock MCP가 다음 자료를 반환했습니다: {titles}",
        laws=laws,
        cases=cases,
        sources=[item.source_name for item in documents],
        disclaimer=DISCLAIMER,
        trace=[
            {"stage": "request_validated", "status": "ok"},
            {"stage": "mcp_tool_called", "tool": "search_legal_documents"},
            {"stage": "mock_documents_received", "count": len(documents)},
        ],
        is_mock=True,
    )

