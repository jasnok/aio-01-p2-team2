import uuid

from backend.app.mcp_clients.legal_mcp import search_legal_documents
from backend.app.schemas.legal import Evidence, LegalQuestionRequest, LegalQuestionResponse


DISCLAIMER = "이 결과는 서버 연결 확인용 Mock이며 법률 자문이나 실제 법률 정보가 아닙니다."


def answer_question(request: LegalQuestionRequest) -> LegalQuestionResponse:
    tool_result = search_legal_documents(request.question, request.category)
    if not tool_result.get("success"):
        raise RuntimeError(tool_result.get("error", {}).get("message", "MCP Tool 실행 실패"))

    documents = [Evidence.model_validate(item) for item in tool_result["data"]["items"]]
    laws = [item for item in documents if item.source.source_type == "law"]
    cases = [item for item in documents if item.source.source_type == "case"]
    titles = ", ".join(item.title for item in documents)

    return LegalQuestionResponse(
        request_id=f"req-{uuid.uuid4()}",
        agent_id=request.category,
        termination_reason="model_finished",
        question_summary=f"{request.category} 카테고리 Mock 검색",
        key_issues=["Mock 연결 계약 확인"],
        answer=f"서버 연결에 성공했습니다. Mock MCP가 다음 자료를 반환했습니다: {titles}",
        related_laws=laws,
        similar_cases=cases,
        sources=list({item.source.source_id: item.source for item in documents}.values()),
        cautions=[DISCLAIMER],
        is_mock=True,
    )
