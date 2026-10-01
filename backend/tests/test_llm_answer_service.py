import asyncio

from backend.app.agents.models import AnswerDraft
from backend.app.schemas.legal import Evidence, Source
from backend.app.services import legal_question_service


def make_evidence() -> Evidence:
    return Evidence(
        evidence_id="law-1",
        document_id="law-1",
        title="테스트 법령",
        content="테스트 법령의 근거 본문입니다.",
        source=Source(
            source_id="law-1",
            title="공식 출처",
            source_type="law",
            url="https://example.com/law-1",
        ),
        law_name="테스트법",
        article_number="제1조",
    )


def configure_openai_provider(monkeypatch, provider) -> None:
    settings = type("Settings", (), {"llm_provider": "openai"})()
    monkeypatch.setattr(legal_question_service, "get_settings", lambda: settings)
    monkeypatch.setattr(legal_question_service, "get_provider", lambda _name: provider)


def test_answer_with_llm_accepts_retrieved_evidence_only(monkeypatch) -> None:
    class Provider:
        def generate_structured(self, system_prompt, message, response_schema):
            assert response_schema is AnswerDraft
            assert "law-1" in message
            return type(
                "Result",
                (),
                {
                    "output": {
                        "question_summary": "법령 근거를 확인했습니다.",
                        "answer": "제공된 법령 근거를 확인해 주세요.",
                        "key_issues": ["적용 조문"],
                        "cautions": ["추가 사실 확인이 필요합니다."],
                        "used_evidence_ids": ["law-1"],
                        "claims": [{"text": "제공된 법령 근거를 확인해 주세요.",
                                    "citations": [{"evidence_id": "law-1", "quote": "테스트 법령의 근거 본문"}]}],
                    }
                },
            )()

    configure_openai_provider(monkeypatch, Provider())

    draft, llm_used = asyncio.run(
        legal_question_service.answer_with_llm(
            category="housing",
            question="계약 종료 후 보증금을 받지 못했습니다.",
            evidence=[make_evidence()],
        )
    )

    assert llm_used is True
    assert draft.used_evidence_ids == ["law-1"]
    assert draft.answer == "제공된 법령 근거를 확인해 주세요."


def test_answer_with_llm_falls_back_when_citation_is_not_retrieved(monkeypatch) -> None:
    class Provider:
        def generate_structured(self, system_prompt, message, response_schema):
            return type(
                "Result",
                (),
                {
                    "output": {
                        "question_summary": "근거 없음",
                        "answer": "확인되지 않은 결론",
                        "used_evidence_ids": ["not-retrieved"],
                    }
                },
            )()

    configure_openai_provider(monkeypatch, Provider())

    draft, llm_used = asyncio.run(
        legal_question_service.answer_with_llm(
            category="housing",
            question="계약 종료 후 보증금을 받지 못했습니다.",
            evidence=[make_evidence()],
        )
    )

    assert llm_used is False
    assert draft.used_evidence_ids == ["law-1"]
    assert "확인되지 않은 결론" not in draft.answer


def test_fabricated_supporting_quote_causes_visible_fallback(monkeypatch):
    class Provider:
        def generate_structured(self, *args):
            return type("Result", (), {"output": {
                "question_summary": "검증", "answer": "허위 주장",
                "used_evidence_ids": ["law-1"],
                "claims": [{"text": "허위 주장", "citations": [
                    {"evidence_id": "law-1", "quote": "원문에 없는 문장"}]}],
            }})()
    configure_openai_provider(monkeypatch, Provider())
    diagnostics = {}
    draft, used = asyncio.run(legal_question_service.answer_with_llm(
        category="housing", question="보증금 반환", evidence=[make_evidence()], diagnostics=diagnostics))
    assert not used
    assert diagnostics["validation_error"] == "quote_not_in_evidence"
    assert "허위 주장" not in draft.answer


def test_exact_supporting_quote_is_accepted(monkeypatch):
    class Provider:
        def generate_structured(self, *args):
            return type("Result", (), {"output": {
                "question_summary": "검증", "answer": "근거 확인",
                "used_evidence_ids": ["law-1"],
                "claims": [{"text": "근거 확인", "citations": [
                    {"evidence_id": "law-1", "quote": "테스트 법령의 근거 본문"}]}],
            }})()
    configure_openai_provider(monkeypatch, Provider())
    diagnostics = {}
    _, used = asyncio.run(legal_question_service.answer_with_llm(
        category="housing", question="보증금 반환", evidence=[make_evidence()], diagnostics=diagnostics))
    assert used
    assert diagnostics["citation_validation"] == "quotes_verified"


def test_used_ids_are_derived_from_validated_citations(monkeypatch):
    class Provider:
        def generate_structured(self, *args):
            return type("Result", (), {"output": {
                "question_summary": "검증", "answer": "근거 확인", "used_evidence_ids": [],
                "claims": [{"text": "근거 확인", "citations": [
                    {"evidence_id": "law-1", "quote": "테스트 법령의 근거 본문"}]}],
            }})()
    configure_openai_provider(monkeypatch, Provider())
    diagnostics = {}
    draft, used = asyncio.run(legal_question_service.answer_with_llm(
        category="housing", question="보증금 반환", evidence=[make_evidence()], diagnostics=diagnostics))
    assert used
    assert draft.used_evidence_ids == ["law-1"]
    assert diagnostics["citation_ids_normalized"]
