from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client
from frontend.components.result_export import build_analysis_markdown
from frontend.services.api_legal_service import ApiLegalService


def test_consultation_only_response_is_valid_visible_and_exportable(monkeypatch):
    payload = {
        "request_id": "consultation-test", "agent_id": "consumer",
        "status": "completed", "termination_reason": "model_finished",
        "question_summary": "상담사례 요약", "answer": "근거를 확인하세요.",
        "is_mock": False,
        "consultations": [{
            "evidence_id": "consultation-1", "document_id": "1",
            "title": "할부 전환 상담", "content": "상담사례 본문입니다.",
            "source": {"source_id": "1", "title": "한국소비자원",
                       "source_type": "consultation", "url": "https://example.test/source"},
        }],
    }
    monkeypatch.setattr(backend_client, "_request", lambda *args, **kwargs: payload)
    result = ApiLegalService("test-session").analyze_case("consumer", "할부 전환에 대해 알려주세요.")
    assert result["result_state"] == "completed"
    assert result["related_laws"] == result["similar_cases"] == []
    assert result["consultations"][0]["source"]["source_type"] == "consultation"
    exported = build_analysis_markdown(result)
    assert "상담사례 본문입니다." in exported
    assert "https://example.test/source" not in exported
    app = AppTest.from_string(
        "from frontend.components.answer_view import render_analysis_result\n"
        f"render_analysis_result({ascii(result)})"
    ).run()
    assert not app.exception
    assert any("소비자원 상담사례" in item.value for item in app.markdown), str(app)
    assert any("상담사례 본문입니다." in item.value for item in app.markdown)
    assert not any("검색 결과가 없습니다" in item.value for item in app.info)


def test_legacy_response_without_consultations_stays_compatible(monkeypatch):
    monkeypatch.setattr(backend_client, "_request", lambda *args, **kwargs: {
        "request_id": "empty", "agent_id": "consumer", "status": "completed",
        "termination_reason": "no_results", "question_summary": "없음", "answer": "없음",
    })
    result = ApiLegalService("test").analyze_case("consumer", "관련 자료를 찾아주세요.")
    assert result["consultations"] == []
    assert result["result_state"] == "no_results"
