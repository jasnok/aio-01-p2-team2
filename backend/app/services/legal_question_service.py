import uuid

from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import LegalAgentRuntime
from backend.app.schemas.legal import Evidence, LegalQuestionRequest, LegalQuestionResponse


DISCLAIMER = "이 결과는 서버 연결 확인용 Mock이며 법률 자문이나 실제 법률 정보가 아닙니다."


def search_legal_documents(*_args, **_kwargs) -> dict:
    """기존 Mock 계약 테스트 호환용 함수입니다.

    실제 MCP 모드의 검색은 LegalAgentRuntime → search_cases로 실행합니다.
    """
    return {"success": True, "data": {"items": []}}


def answer_question(request: LegalQuestionRequest) -> LegalQuestionResponse:
    return LegalQuestionResponse(
        request_id=f"req-{uuid.uuid4()}",
        agent_id=request.category,
        termination_reason="model_finished",
        question_summary=f"{request.category} 카테고리 Mock 검색",
        key_issues=["Mock 연결 계약 확인"],
        answer="Mock 모드 사례 분석 응답입니다.",
        cautions=[DISCLAIMER],
        is_mock=True,
    )


async def answer_question_from_mcp(request: LegalQuestionRequest) -> LegalQuestionResponse:
    profile = get_agent_profile(request.category)
    state = AgentState(request_id=f"req-{uuid.uuid4()}", agent_id=profile.agent_id, question=request.question)
    state, raw_evidence = await LegalAgentRuntime().run(profile, state)
    documents = [Evidence.model_validate(item) for item in raw_evidence]
    laws = [item for item in documents if item.source.source_type == "law"]
    cases = [item for item in documents if item.source.source_type == "case"]
    consultations = [
        item for item in documents
        if item.source.source_type == "consultation"
    ]
    sources = list({item.source.source_id: item.source for item in documents}.values())
    answer = (
        "검색된 공식 판례 자료를 바탕으로 확인할 사항을 정리했습니다. 구체적 적용은 사실관계와 원문을 추가로 확인해야 합니다."
        if documents else "현재 검색어로는 충분한 공식 판례 근거를 찾지 못했습니다. 사실관계나 검색어를 보완해 다시 확인해 주세요."
    )
    category_summaries = {
    "labor": "근로·임금 분야의 관련 판례 자료를 검색했습니다.",
    "housing": "임대차·주거 분야의 관련 판례 자료를 검색했습니다.",
    "consumer": "소비자·중고거래 분야의 관련 판례 자료를 검색했습니다.",
    }
    category_key_issues = {
    "labor": ["근로관계 종료 여부", "임금·퇴직금 지급 내역", "요청 기록"],
    "housing": ["임대차 계약 기간", "보증금 지급 내역", "계약 종료·반환 요청 기록"],
    "consumer": ["거래 약속 내용", "결제·송금 내역", "판매자와의 대화 기록"],
    }
    return LegalQuestionResponse(
        request_id=state.request_id, agent_id=request.category, status="completed",
        termination_reason=state.termination_reason or "model_finished",
        question_summary=category_summaries.get(
        request.category,
        "생활 법률 분야의 관련 자료를 검색했습니다.",
        ),
        key_issues=category_key_issues.get(
        request.category,
        ["사실관계", "관련 자료", "요청 기록"],
        ),
        related_laws=laws, similar_cases=cases, consultations=consultations,
        sources=sources,
        cautions=["검색 결과는 법률 자문이나 결과 보장이 아닙니다."], is_mock=False,
        answer=answer,
    )
