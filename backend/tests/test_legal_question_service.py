import asyncio

from backend.app.agents.models import AgentState
from backend.app.schemas.legal import LegalQuestionRequest
from backend.app.services import legal_question_service


def test_consumer_response_places_consultations_in_separate_list(monkeypatch) -> None:
    async def fake_run(self, profile, state):
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

    response = asyncio.run(
        legal_question_service.answer_question_from_mcp(
            LegalQuestionRequest(
                session_id="consumer-test",
                category="consumer",
                question="할부 결제한 물건이 배송되지 않았습니다.",
            )
        )
    )

    assert response.related_laws == []
    assert response.similar_cases == []
    assert len(response.consultations) == 1
    assert response.consultations[0].source.source_type == "consultation"
    assert response.sources[0].source_type == "consultation"
