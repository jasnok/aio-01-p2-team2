import asyncio

from backend.app.agents.models import AgentState, IntakeResult
from backend.app.schemas.legal import LegalQuestionRequest
from backend.app.services import legal_question_service


def test_consumer_response_places_consultations_in_separate_list(monkeypatch) -> None:
    async def fake_assess(self, category, question, event_callback=None):
        return IntakeResult(
            is_ready_for_search=True, status="sufficient", message="검색을 진행할 수 있습니다.",
        )

    async def fake_run(self, profile, state, event_callback=None):
        state.status = "completed"
        state.termination_reason = "model_finished"
        return state, [
            {
                "evidence_id": "consultation-1",
                "document_id": "1",
                "title": "소비자원 상담사례",
                "content": "상담사례 본문",
                "source": {
                    "source_id": "1",
                    "title": "한국소비자원 품목별 피해구제 사례",
                    "source_type": "consultation",
                    "url": "https://example.com/consultation-1",
                },
                "metadata": {
                    "document_type": "CONSULTATION",
                    "category": "consumer",
                },
            }
        ]

    monkeypatch.setattr(
        legal_question_service.LegalAgentRuntime,
        "run",
        fake_run,
    )
    monkeypatch.setattr(legal_question_service.IntakeAgent, "assess", fake_assess)

    response = asyncio.run(
        legal_question_service.answer_question_from_mcp(
            LegalQuestionRequest(
                session_id="consumer-test",
                category="consumer",
                question=(
                    "할부 결제한 물건이 배송되지 않았고 "
                    "카드사에 문의했습니다."
                ),
            )
        )
    )

    assert response.related_laws == []
    assert response.similar_cases == []
    assert len(response.consultations) == 1
    assert response.consultations[0].source.source_type == "consultation"
    assert response.sources[0].source_type == "consultation"
    assert response.input_assessment.status == "sufficient"


def test_incomplete_question_skips_mcp_search(monkeypatch) -> None:
    async def fake_assess(self, category, question, event_callback=None):
        return IntakeResult(
            is_ready_for_search=False,
            status="needs_clarification",
            message="질문의 핵심을 확인하기 어렵습니다.",
            follow_up_questions=["어떤 일이 있었는지 알려주세요."],
        )

    async def fail_if_runtime_is_called(self, profile, state):
        raise AssertionError("정보가 부족한 질문은 MCP 검색을 실행하면 안 됩니다.")

    monkeypatch.setattr(
        legal_question_service.LegalAgentRuntime,
        "run",
        fail_if_runtime_is_called,
    )
    monkeypatch.setattr(legal_question_service.IntakeAgent, "assess", fake_assess)

    response = asyncio.run(
        legal_question_service.answer_question_from_mcp(
            LegalQuestionRequest(
                session_id="intake-test",
                category="consumer",
                question="카드로 결제했는데 물건이 배송되지 않았습니다.",
            )
        )
    )

    assert response.status == "stopped"
    assert response.termination_reason == "needs_clarification"
    assert response.follow_up_questions == ["어떤 일이 있었는지 알려주세요."]
    assert response.input_assessment.status == "needs_clarification"
