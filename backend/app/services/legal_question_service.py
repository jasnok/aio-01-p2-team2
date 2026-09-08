import uuid

from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import LegalAgentRuntime
from backend.app.schemas.legal import Evidence, LegalQuestionRequest, LegalQuestionResponse
from backend.app.agents.intake_agent import IntakeAgent
from backend.app.agents.answer_agent import AnswerAgent


DISCLAIMER = "이 결과는 서버 연결 확인용 Mock이며 법률 자문이나 실제 법률 정보가 아닙니다."
def create_clarification_response(
    request: LegalQuestionRequest,
    is_mock: bool,
) -> LegalQuestionResponse | None:
    intake_result = IntakeAgent().assess(
        request.category,
        request.question,
    )

    if intake_result.is_ready_for_search:
        return None

    return LegalQuestionResponse(
        request_id=f"req-{uuid.uuid4()}",
        agent_id=request.category,
        status="stopped",
        termination_reason="needs_clarification",
        question_summary="정확한 검색을 위해 추가 정보가 필요합니다.",
        answer="아래 질문에 답해 주시면 관련 법령과 사례를 더 정확하게 검색할 수 있습니다.",
        follow_up_questions=intake_result.follow_up_questions,
        cautions=[
            "추가 정보는 검색 정확도를 높이기 위한 것이며 법률 판단이 아닙니다.",
        ],
        is_mock=is_mock,
    )

def search_legal_documents(*_args, **_kwargs) -> dict:
    """기존 Mock 계약 테스트 호환용 함수입니다.

    실제 MCP 모드의 검색은 LegalAgentRuntime → search_cases로 실행합니다.
    """
    return {"success": True, "data": {"items": []}}


def answer_question(
    request: LegalQuestionRequest,
) -> LegalQuestionResponse:
    clarification_response = create_clarification_response(
        request,
        is_mock=True,
    )

    if clarification_response is not None:
        return clarification_response

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

async def answer_question_from_mcp(
    request: LegalQuestionRequest,
) -> LegalQuestionResponse:
    clarification_response = create_clarification_response(
        request,
        is_mock=False,
    )

    if clarification_response is not None:
        return clarification_response

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
    draft = AnswerAgent().create_draft(
        category=request.category,
        question=request.question,
        evidence=documents,
    )
    return LegalQuestionResponse(
        request_id=state.request_id, agent_id=request.category, status="completed",
        termination_reason=state.termination_reason or "model_finished",
        question_summary=draft.question_summary,
        key_issues=draft.key_issues,
        related_laws=laws, similar_cases=cases, consultations=consultations,
        sources=sources,
        cautions=[
            *draft.cautions,
            *(
                ["공식 근거가 3건 미만이라 추가 확인이 필요합니다."]
                if state.termination_reason == "insufficient_evidence"
                else []
        ),
        ], is_mock=False,
        answer=draft.answer,
    )
