from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import legal as legal_router


client = TestClient(app)


def evidence(source_type: str, document_id: str) -> dict:
    return {
        "evidence_id": f"{source_type}-{document_id}",
        "document_id": document_id,
        "title": f"{source_type} 자료",
        "content": "공식 검색 자료입니다.",
        "source": {
            "source_id": document_id,
            "title": "공식 출처",
            "source_type": source_type,
            "url": "https://example.com/source",
        },
    }


def test_law_search_runs_law_tool_and_returns_evidence(monkeypatch) -> None:
    async def fake_run(self, profile, state, tool_name, top_k):
        assert profile.agent_id == "housing"
        assert tool_name == "search_laws"
        assert top_k == 2
        return state, [evidence("law", "700")]

    monkeypatch.setattr(legal_router.LegalAgentRuntime, "run_single_tool", fake_run)

    response = client.get(
        "/api/legal/laws",
        params={"category": "housing", "query": "보증금 반환", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "보증금 반환"
    assert payload["category"] == "housing"
    assert payload["total"] == 1
    assert payload["items"][0]["source"]["source_type"] == "law"


def test_case_search_returns_empty_array_when_no_result(monkeypatch) -> None:
    async def fake_run(self, profile, state, tool_name, top_k):
        assert tool_name == "search_cases"
        return state, []

    monkeypatch.setattr(legal_router.LegalAgentRuntime, "run_single_tool", fake_run)

    response = client.get(
        "/api/legal/cases",
        params={"category": "labor", "query": "존재하지 않는 검색어"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_consultation_search_returns_mcp_error(monkeypatch) -> None:
    async def fake_run(self, profile, state, tool_name, top_k):
        assert tool_name == "search_consultations"
        raise RuntimeError("MCP 연결 실패")

    monkeypatch.setattr(legal_router.LegalAgentRuntime, "run_single_tool", fake_run)

    response = client.get(
        "/api/legal/consultations",
        params={"category": "consumer", "query": "할부항변권"},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "MCP_UNAVAILABLE"


def test_search_rejects_whitespace_only_query() -> None:
    response = client.get(
        "/api/legal/laws",
        params={"category": "housing", "query": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
