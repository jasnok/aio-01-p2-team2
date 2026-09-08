from backend.app.agents.intake_agent import IntakeAgent


def test_consumer_question_returns_follow_up_question() -> None:
    result = IntakeAgent().assess(
        "consumer",
        "카드 할부로 결제했는데 물건이 배송되지 않았습니다.",
    )

    assert result.is_ready_for_search is False
    assert result.missing_fields == ["contact_history"]
    assert result.follow_up_questions == [
        "판매자 또는 카드사에 문의했는지 알려주세요."
    ]


def test_labor_question_is_ready_when_required_information_exists() -> None:
    result = IntakeAgent().assess(
        "labor",
        (
            "2026년 8월 1일 퇴사했고 "
            "3년간 근무했습니다. "
            "회사에 퇴직금 지급 요청 문자도 보냈습니다."
        ),
    )

    assert result.is_ready_for_search is True
    assert result.missing_fields == []
    assert result.follow_up_questions == []

def test_general_legal_question_is_ready_for_search() -> None:
    result = IntakeAgent().assess(
        "housing",
        (
            "주택 임대차 계약이 끝났는데 "
            "임대인이 보증금을 돌려주지 않습니다. "
            "어떤 법 조문을 확인해야 하나요?"
        ),
    )

    assert result.is_ready_for_search is True
    assert result.missing_fields == []
    assert result.follow_up_questions == []