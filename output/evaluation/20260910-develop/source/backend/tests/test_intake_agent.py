import asyncio
import time

import pytest

from backend.app.agents.intake_agent import IntakeAgent, IntakeAssessmentError
from backend.app.providers.models import ProviderResult


def configure_provider(monkeypatch, output, *, timeout: float = 0.1):
    settings = type("Settings", (), {
        "llm_provider": "openai",
        "input_assessment_timeout_seconds": timeout,
    })()

    class Provider:
        calls = 0

        def generate_structured(self, system_prompt, message, response_schema):
            self.calls += 1
            value = output[self.calls - 1] if isinstance(output, list) else output
            if isinstance(value, Exception):
                raise value
            return ProviderResult("openai", "test", value, 0)

    provider = Provider()
    monkeypatch.setattr("backend.app.agents.intake_agent.get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.agents.intake_agent.get_provider", lambda _name: provider)
    return provider


@pytest.mark.parametrize(
    ("category", "question"),
    [
        ("housing", "주택 임대차 계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다. 어떤 법 조문을 확인해야 하나요?"),
        ("labor", "퇴직했는데 회사가 퇴직금을 지급하지 않습니다. 퇴직금 지급 기한과 관련 법 조문을 알려주세요."),
        ("consumer", "신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?"),
    ],
)
def test_representative_questions_continue_to_search(monkeypatch, category, question) -> None:
    provider = configure_provider(monkeypatch, {
        "status": "proceed_with_caution",
        "message": "일반 법률 검색은 가능하지만 개별 결론에는 추가 사실 확인이 필요합니다.",
        "follow_up_questions": ["관련 자료가 있으면 함께 확인해 주세요."],
        "cautions": ["검색 결과는 개별 사건의 결론이 아닙니다."],
    })

    result = asyncio.run(IntakeAgent().assess(category, question))

    assert result.is_ready_for_search is True
    assert result.status == "proceed_with_caution"
    assert provider.calls == 1


def test_vague_question_needs_clarification(monkeypatch) -> None:
    configure_provider(monkeypatch, {
        "status": "needs_clarification",
        "message": "어떤 법률 문제인지 확인이 필요합니다.",
        "follow_up_questions": ["어떤 일이 있었는지 알려주세요."],
    })

    result = asyncio.run(IntakeAgent().assess("housing", "문제가 생겼어요. 도와주세요."))

    assert result.is_ready_for_search is False
    assert result.status == "needs_clarification"
    assert result.follow_up_questions == ["어떤 일이 있었는지 알려주세요."]


def test_invalid_output_retries_only_once(monkeypatch) -> None:
    provider = configure_provider(monkeypatch, [
        {"status": "unknown", "message": "잘못된 상태"},
        {"status": "sufficient", "message": "법령 검색을 진행할 수 있습니다."},
    ])

    result = asyncio.run(IntakeAgent().assess("labor", "근로기준법을 알려주세요."))

    assert result.status == "sufficient"
    assert provider.calls == 2


def test_general_law_question_returns_complete_optional_checks(monkeypatch) -> None:
    configure_provider(monkeypatch, {
        "status": "sufficient",
        "message": "일반 법령 검색을 진행할 수 있습니다.",
        "checks": {
            "situation": "met",
            "timing": "not_required",
            "relationship": "not_required",
            "request_evidence": "not_required",
        },
    })

    result = asyncio.run(IntakeAgent().assess("labor", "근로기준법을 알려주세요."))

    assert result.status == "sufficient"
    assert result.checks is not None
    assert result.checks.timing == "not_required"
    assert result.checks.request_evidence == "not_required"


def test_partial_checks_are_retried_as_invalid_structured_output(monkeypatch) -> None:
    provider = configure_provider(monkeypatch, [
        {
            "status": "sufficient",
            "message": "검색할 수 있습니다.",
            "checks": {"situation": "met"},
        },
        {"status": "sufficient", "message": "검색할 수 있습니다."},
    ])

    result = asyncio.run(IntakeAgent().assess("labor", "근로기준법을 알려주세요."))

    assert result.checks is None
    assert provider.calls == 2


def test_follow_up_request_is_assessed_again_without_repeating_the_original_question(monkeypatch) -> None:
    original = "임대인이 보증금을 돌려주지 않습니다."
    follow_up = f"{original} 계약 종료일은 2026년 8월 1일이고 내용증명을 보냈습니다."
    provider = configure_provider(monkeypatch, {
        "status": "proceed_with_caution",
        "message": "제공한 사실을 기준으로 검색을 진행합니다.",
        "follow_up_questions": [
            follow_up,
            "반환을 요구한 시점이 있다면 확인해 주세요.",
        ],
    })

    result = asyncio.run(IntakeAgent().assess("housing", follow_up))

    assert result.is_ready_for_search is True
    assert provider.calls == 1
    assert result.follow_up_questions == ["반환을 요구한 시점이 있다면 확인해 주세요."]


def test_timeout_is_not_disguised_as_clarification(monkeypatch) -> None:
    class SlowProvider:
        def generate_structured(self, *_args):
            time.sleep(0.05)
            return ProviderResult("openai", "test", {"status": "sufficient", "message": "늦음"}, 50)

    settings = type("Settings", (), {"llm_provider": "openai", "input_assessment_timeout_seconds": 0.001})()
    monkeypatch.setattr("backend.app.agents.intake_agent.get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.agents.intake_agent.get_provider", lambda _name: SlowProvider())

    with pytest.raises(IntakeAssessmentError):
        asyncio.run(IntakeAgent().assess("consumer", "카드사에 문의했는데 답을 받지 못했습니다."))
