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


def test_labor_runtime_calls_search_cases_and_records_trace(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        assert category == "labor"
        assert top_k == 3
        return {"success": True, "data": []}

    monkeypatch.setattr("backend.app.agents.runtime.search_cases", fake_search_cases)
    state, evidence = asyncio.run(
        LegalAgentRuntime().run(
            LABOR_AGENT,
            AgentState(request_id="req-test", agent_id="labor", question="퇴직금을 받지 못했습니다."),
        )
    )
    assert evidence == []
    assert state.status == "completed"
    assert state.termination_reason == "no_results"
    assert state.tool_calls == 1
    assert state.evidence_count == 0
    assert state.trace[-1]["tool"] == "search_cases"

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


def test_consumer_runtime_can_use_common_search_cases(monkeypatch) -> None:
    async def fake_search_cases(query: str, category: str, top_k: int) -> dict:
        assert category == "consumer"
        assert top_k == 3
        return {
            "success": True,
            "data": [],
        }

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

    assert evidence == []
    assert state.status == "completed"
    assert state.termination_reason == "no_results"
