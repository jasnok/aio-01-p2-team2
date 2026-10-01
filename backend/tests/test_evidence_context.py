import asyncio
import json
import pytest
from backend.app.agents.models import SpanAnswerDraft
from backend.app.schemas.legal import Evidence, Source
from backend.app.services.evidence_context import build_context, resolve_span_draft
from backend.app.services import legal_question_service as service


def evidence(number=1, source_type="law", content="퇴직금의 지급 기한은 원문에서 확인해야 합니다."):
    return Evidence(evidence_id=f"{source_type}-{number}", document_id=str(number), title="근거",
        content=content, score=0.7, source=Source(source_id=str(number), title="출처",
                                               source_type=source_type, url="https://example.com"))


def test_context_bounds_exact_quotes_and_preserves_source_diversity():
    rows = [evidence(n, source_type, "관계없는 내용입니다. " * 200 + "퇴직금 지급 기한을 확인하세요.")
            for n in range(3) for source_type in ("law", "case", "consultation")]
    docs, spans = build_context("퇴직금 지급 기한", rows)
    assert len(docs) == 6
    assert {doc["source_type"] for doc in docs} == {"law", "case", "consultation"}
    assert len(spans) <= 18
    originals = {row.evidence_id: row.content for row in rows}
    assert all(len(item["quote"]) <= 2400 and item["quote"] in originals[item["evidence_id"]]
               for item in spans.values())
    assert any("퇴직금 지급 기한" in item["quote"] for item in spans.values())


def test_server_resolves_span_id_and_binds_answer_to_cited_claim():
    _, spans = build_context("퇴직금", [evidence()])
    output = {"question_summary": "요약", "claims": [{"text": "기한을 확인하세요.", "span_ids": list(spans)}]}
    draft = resolve_span_draft(output, spans)
    assert draft.answer == draft.claims[0].text
    assert draft.claims[0].citations[0].quote == evidence().content
    assert draft.used_evidence_ids == ["law-1"]
    output["claims"][0]["span_ids"] = ["invented"]
    with pytest.raises(ValueError, match="unknown_citation_span"):
        resolve_span_draft(output, spans)


def test_span_generation_uses_existing_ids_without_model_copying_quotes(monkeypatch):
    class Provider:
        def generate_structured(self, prompt, message, schema):
            assert schema is SpanAnswerDraft
            payload = json.loads(message)
            span_id = payload["evidence"][0]["excerpts"][0]["span_id"]
            return type("Result", (), {"output": {"question_summary": "요약",
                "claims": [{"text": "원문 확인이 필요합니다.", "span_ids": [span_id]}]}})()
    monkeypatch.setattr(service, "get_settings", lambda: type("Settings", (), {
        "llm_provider": "openai", "citation_mode": "spans"})())
    monkeypatch.setattr(service, "get_provider", lambda name: Provider())
    diagnostics = {}
    draft, used = asyncio.run(service.answer_with_llm(category="labor", question="퇴직금",
        evidence=[evidence()], diagnostics=diagnostics))
    assert used and diagnostics["citation_mode"] == "spans"
    assert draft.claims[0].citations[0].quote == evidence().content


def test_unknown_generated_span_falls_back(monkeypatch):
    class Provider:
        def generate_structured(self, *args):
            return type("Result", (), {"output": {"question_summary": "요약",
                "claims": [{"text": "허위 주장", "span_ids": ["invented"]}]}})()
    monkeypatch.setattr(service, "get_settings", lambda: type("Settings", (), {
        "llm_provider": "openai", "citation_mode": "spans"})())
    monkeypatch.setattr(service, "get_provider", lambda name: Provider())
    diagnostics = {}
    draft, used = asyncio.run(service.answer_with_llm(category="labor", question="퇴직금",
        evidence=[evidence()], diagnostics=diagnostics))
    assert not used and diagnostics["validation_error"] == "invalid_citation_span"
    assert "허위 주장" not in draft.answer
