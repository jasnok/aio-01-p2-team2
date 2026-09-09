from frontend.clients import backend_client
from frontend.services.api_legal_service import ApiLegalService
from frontend.services import factory
from types import SimpleNamespace


def test_api_service_analyzes_and_adapts_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        backend_client,
        "ask_legal_question",
        lambda *args, **kwargs: {
            "request_id": "req-1",
            "agent_id": "housing",
            "status": "completed",
            "termination_reason": "model_finished",
            "question_summary": "요약",
            "key_issues": ["쟁점"],
            "answer": "답변",
            "related_laws": [{"title": "주택임대차보호법", "content": "법령 내용", "source": {"title": "법제처", "url": "https://example.test/law"}}],
            "similar_cases": [{"title": "보증금 사건", "court": "대법원", "score": 0.8, "case_number": "2026다1", "decided_at": "2026-01-01", "judgment_result": "일부 승소"}],
            "sources": [],
            "follow_up_questions": [],
            "cautions": [],
            "is_mock": False,
        },
    )

    result = ApiLegalService("web-test").analyze_case("housing", "보증금을 돌려받지 못했습니다.")

    assert result["question"] == "보증금을 돌려받지 못했습니다."
    assert result["related_laws"][0]["detail"] == "법령 내용"
    assert result["similar_cases"][0]["date"] == "2026-01-01"
    assert result["result_state"] == "completed"


def test_api_service_calls_search_and_catalog_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(backend_client, "search_laws", lambda *args, **kwargs: {"items": [{"title": "법령", "content": "내용"}]})
    monkeypatch.setattr(backend_client, "search_cases", lambda *args, **kwargs: {"items": [{"title": "판례"}]})
    monkeypatch.setattr(backend_client, "search_terms", lambda *args, **kwargs: {"items": [{"term": "보증금", "description": "설명"}]})
    monkeypatch.setattr(backend_client, "get_category_catalog", lambda *args, **kwargs: {"terms": [["임차인", "설명"]]})
    service = ApiLegalService("web-test")

    assert service.search_laws("housing", "보증금")[0]["title"] == "법령"
    assert service.search_cases("housing", "보증금")[0]["case_number"] == "사건번호 없음"
    assert service.search_terms("housing", "보증금") == [("보증금", "설명")]
    assert service.search_terms("housing", "") == [("임차인", "설명")]


def test_factory_selects_api_service(monkeypatch) -> None:
    monkeypatch.setattr(factory, "get_frontend_settings", lambda: SimpleNamespace(frontend_data_mode="api"))
    monkeypatch.setattr(factory, "st", SimpleNamespace(session_state=SimpleNamespace(current_user={"id": "guest-web-api-test"}, auth_token=None)))

    service = factory.get_legal_service()

    assert isinstance(service, ApiLegalService)
    assert service.session_id == "guest-web-api-test"
