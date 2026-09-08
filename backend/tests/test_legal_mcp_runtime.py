import asyncio
import pytest
from fastapi.testclient import TestClient

from backend.app.agents.models import AgentState
from backend.app.agents.profiles import (
    LABOR_AGENT,
    HOUSING_AGENT,
    CONSUMER_AGENT,
)
from backend.app.agents.runtime import LegalAgentRuntime
from backend.app.main import app
from backend.app.routers import legal as legal_router


def test_labor_runtime_retries_with_documents_when_cases_are_insufficient(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        assert category == "labor"
        assert top_k == 3
        return {
            "success": True,
            "data": [
                {"evidence_id": "case-1"},
                {"evidence_id": "case-2"},
            ],
        }

    async def fake_search_legal_documents(query: str, category: str, top_k: int) -> dict:
        assert category == "labor"
        return {
            "success": True,
            "data": {"items": [{"evidence_id": "law-1"}]},
        }

    monkeypatch.setattr("backend.app.agents.runtime.search_cases", fake_search_cases)
    monkeypatch.setattr(
        "backend.app.agents.runtime.search_legal_documents",
        fake_search_legal_documents,
    )
    state, evidence = asyncio.run(
        LegalAgentRuntime().run(
            LABOR_AGENT,
            AgentState(request_id="req-test", agent_id="labor", question="퇴직금을 받지 못했습니다."),
        )
    )
    assert [item["evidence_id"] for item in evidence] == ["case-1", "case-2", "law-1"]
    assert state.status == "completed"
    assert state.termination_reason == "model_finished"
    assert state.tool_calls == 2
    assert state.evidence_count == 3
    assert state.trace[-1]["tool"] == "search_legal_documents"

def test_labor_runtime_raises_error_when_mcp_fails(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        return {
            "success": False,
            "message": "MCP 연결 실패",
        }

    monkeypatch.setattr(
        "backend.app.agents.runtime.search_cases",
        fake_search_cases,
    )

    state = AgentState(
        request_id="req-mcp-fail",
        agent_id="labor",
        question="퇴직금을 받지 못했습니다.",
    )

    with pytest.raises(RuntimeError, match="MCP 연결 실패"):
        asyncio.run(
            LegalAgentRuntime().run(
                LABOR_AGENT,
                state,
            )
        )

def test_real_mode_uses_agent_runtime_response(monkeypatch) -> None:
    async def fake_answer(request):
        from backend.app.schemas.legal import LegalQuestionResponse
        return LegalQuestionResponse(
            request_id="req-real", agent_id="labor", termination_reason="model_finished",
            question_summary="실제 MCP 테스트", answer="검색 결과", is_mock=False,
        )

    settings = type("Settings", (), {"backend_mock_mode": False})()
    monkeypatch.setattr(legal_router, "get_settings", lambda: settings)
    monkeypatch.setattr(legal_router, "answer_question_from_mcp", fake_answer)
    response = TestClient(app).post("/api/legal/questions", json={
        "session_id": "real-mode-test", "category": "labor", "question": "퇴직금을 받지 못했습니다.",
    })
    assert response.status_code == 200
    assert response.json()["is_mock"] is False


def test_housing_runtime_can_use_common_search_cases(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        assert category == "housing"
        assert top_k == 3
        return {
            "success": True,
            "data": [],
        }

    monkeypatch.setattr(
        "backend.app.agents.runtime.search_cases",
        fake_search_cases,
    )

    async def fake_search_legal_documents(query: str, category: str, top_k: int) -> dict:
        return {"success": True, "data": {"items": []}}

    monkeypatch.setattr(
        "backend.app.agents.runtime.search_legal_documents",
        fake_search_legal_documents,
    )

    state = AgentState(
        request_id="req-housing",
        agent_id="housing",
        question="계약이 끝났는데 보증금을 받지 못했습니다.",
    )

    state, evidence = asyncio.run(
        LegalAgentRuntime().run(
            HOUSING_AGENT,
            state,
        )
    )

    assert evidence == []
    assert state.status == "completed"
    assert state.termination_reason == "no_results"


def test_consumer_runtime_returns_three_results_for_each_evidence_type(monkeypatch) -> None:
    def make_evidence(source_type: str, prefix: str) -> list[dict]:
        return [
            {
                "evidence_id": f"{prefix}-{number}",
                "document_id": f"{prefix}-{number}",
                "title": f"{source_type} {number}",
                "content": f"{source_type} 본문 {number}",
                "source": {
                    "source_id": f"{prefix}-{number}",
                    "title": f"{source_type} 출처",
                    "source_type": source_type,
                    "url": f"https://example.com/{prefix}-{number}",
                },
            }
            for number in range(1, 4)
        ]

    async def fake_search_laws(query: str, category: str, top_k: int) -> dict:
        assert category == "consumer"
        assert top_k == 3
        return {"success": True, "data": make_evidence("law", "law")}

    async def fake_search_consultations(query: str, category: str, top_k: int) -> dict:
        assert category == "consumer"
        assert top_k == 3
        return {
            "success": True,
            "data": make_evidence("consultation", "consultation"),
        }

    monkeypatch.setattr(
        "backend.app.agents.runtime.search_consultations",
        fake_search_consultations,
    )

    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        assert category == "consumer"
        assert top_k == 3
        return {"success": True, "data": make_evidence("case", "case")}

    monkeypatch.setattr(
        "backend.app.agents.runtime.search_laws",
        fake_search_laws,
    )
    monkeypatch.setattr(
        "backend.app.agents.runtime.search_cases",
        fake_search_cases,
    )

    state = AgentState(
        request_id= "req_consumer",
        agent_id= "consumer",
        question= "중고거래 물건을 받지 못했습니다.",
    )

    state, evidence = asyncio.run(
        LegalAgentRuntime().run(
            CONSUMER_AGENT,
            state,
        )
    )

    assert len(evidence) == 9
    assert len([item for item in evidence if item["source"]["source_type"] == "law"]) == 3
    assert len([item for item in evidence if item["source"]["source_type"] == "consultation"]) == 3
    assert len([item for item in evidence if item["source"]["source_type"] == "case"]) == 3
    assert state.status == "completed"
    assert state.termination_reason == "model_finished"
    assert state.tool_calls == 3


def test_runtime_reports_actual_tool_start_and_completion(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        return {"success": True, "data": []}

    async def fake_search_documents(query: str, category: str, top_k: int) -> dict:
        return {"success": True, "data": {"items": []}}

    events: list[dict] = []

    async def record(event: dict) -> None:
        events.append(event.copy())

    monkeypatch.setattr("backend.app.agents.runtime.search_cases", fake_search_cases)
    monkeypatch.setattr("backend.app.agents.runtime.search_legal_documents", fake_search_documents)
    asyncio.run(
        LegalAgentRuntime().run(
            LABOR_AGENT,
            AgentState(request_id="req-sse", agent_id="labor", question="퇴직금을 받지 못했습니다."),
            event_callback=record,
        )
    )
    assert [event["stage"] for event in events] == ["tool_selected", "tool_completed", "tool_selected", "tool_completed"]
    assert events[0]["tool"] == events[1]["tool"] == "search_cases"
