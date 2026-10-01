import asyncio
import pytest
from backend.app.agents.models import AnswerDraft
from backend.app.services.answer_verification import review_answer
from backend.app.services.text_spans import select_windows
from backend.app.services import legal_question_service as service
from backend.tests.test_evidence_context import evidence


def test_sentence_context_keeps_exception_and_exact_offsets():
    text = "퇴직금은 지급해야 합니다. 다만 해당 조건이 충족되지 않으면 제외합니다. 예외가 적용됩니다."
    windows = select_windows("퇴직금 지급", text)
    assert windows and "다만" in windows[0]["quote"]
    assert all(text[item["start"]:item["end"]] == item["quote"] for item in windows)


def test_oversized_indivisible_clause_is_not_truncated():
    assert select_windows("예외", "본문" * 1500 + "다만 예외입니다.", budget=2400) == []


def test_review_must_cover_every_claim_exactly_once():
    draft = AnswerDraft(question_summary="요약", answer="내용", claims=[{
        "text": "내용", "citations": [{"evidence_id": "law-1", "quote": "원문"}]}])
    class Provider:
        def generate_structured(self, *args):
            return type("Result", (), {"output": {"claims": [{"claim_index": 2, "verdict": "supported", "reason": "확인"}]}})()
    with pytest.raises(ValueError, match="coverage"):
        asyncio.run(review_answer(draft, Provider()))


def test_unsupported_claim_repair_is_bounded_and_falls_back(monkeypatch):
    import json
    from backend.app.agents.models import SpanAnswerDraft
    class Provider:
        calls = 0
        def generate_structured(self, prompt, message, schema):
            self.calls += 1
            if schema is SpanAnswerDraft:
                # Repair input appends feedback after the original JSON.
                data, _ = json.JSONDecoder().raw_decode(message)
                span = data["evidence"][0]["excerpts"][0]["span_id"]
                output = {"question_summary": "요약", "claims": [{"text": "허위 주장", "span_ids": [span]}]}
            else:
                output = {"claims": [{"claim_index": 0, "verdict": "unsupported", "reason": "근거 없음"}]}
            return type("Result", (), {"output": output})()
    provider = Provider()
    monkeypatch.setattr(service, "get_settings", lambda: type("Settings", (), {
        "llm_provider": "openai", "citation_mode": "spans", "semantic_verification_enabled": True,
        "answer_repair_attempts": 1})())
    monkeypatch.setattr(service, "get_provider", lambda name: provider)
    diagnostics = {}
    draft, used = asyncio.run(service.answer_with_llm(category="labor", question="퇴직금",
        evidence=[evidence()], diagnostics=diagnostics))
    assert provider.calls == 4  # generation/review + one repair/review
    assert not used and "허위 주장" not in draft.answer
    assert diagnostics["repair_attempts"] == 1


@pytest.mark.parametrize("repairs,expected_calls", [(0, 2), (1, 4)])
def test_partial_claims_removed_and_context_built_once(monkeypatch, repairs, expected_calls):
    import json
    from types import SimpleNamespace
    from backend.app.agents.models import SpanAnswerDraft
    built = []
    original = service.build_context
    def build(*args, **kwargs):
        built.append(True)
        return original(*args, **kwargs)
    class Provider:
        calls = 0
        async def generate_structured_async(self, prompt, message, schema):
            self.calls += 1
            if schema is SpanAnswerDraft:
                data, _ = json.JSONDecoder().raw_decode(message)
                span = data["evidence"][0]["excerpts"][0]["span_id"]
                output = {"question_summary": "요약", "claims": [
                    {"text": "지원 주장", "span_ids": [span]}, {"text": "부분 주장", "span_ids": [span]}]}
            else:
                output = {"claims": [{"claim_index": 0, "verdict": "supported", "reason": "일치"},
                                     {"claim_index": 1, "verdict": "partial", "reason": "범위 초과"}]}
            return SimpleNamespace(output=output, elapsed_ms=1)
    provider = Provider()
    monkeypatch.setattr(service, "build_context", build)
    clock = iter([0, .01, .20])
    monkeypatch.setattr(service, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(llm_provider="openai",
        citation_mode="spans", semantic_verification_enabled=True, answer_repair_attempts=repairs))
    monkeypatch.setattr(service, "get_provider", lambda name: provider)
    diagnostics = {}
    draft, used = asyncio.run(service.answer_with_llm(category="labor", question="퇴직금",
        evidence=[evidence()], diagnostics=diagnostics))
    assert used and draft.answer == "지원 주장"
    assert provider.calls == expected_calls and len(built) == 1
    assert diagnostics["excluded_claims"] == 1 and diagnostics["repair_attempts"] == repairs
    assert diagnostics["context_ms"] == 10 and diagnostics["generation_ms"] == 200
    assert diagnostics["last_generation_call_ms"] == 1


def test_compact_review_deduplicates_exact_quotes():
    from backend.app.services.answer_verification import review_payload
    draft = AnswerDraft(question_summary="요약", answer="내용", claims=[{
        "text": text, "citations": [{"evidence_id": "law-1", "quote": "동일 원문"}]}
        for text in ("첫 주장", "둘째 주장")])
    payload = review_payload(draft, compact=True)
    assert payload["quotes"] == {"quote-0": "동일 원문"}
    assert all(claim["quote_ids"] == ["quote-0"] for claim in payload["claims"])
