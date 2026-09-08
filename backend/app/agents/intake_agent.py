from backend.app.agents.models import IntakeResult


FOLLOW_UP_QUESTIONS = {
    "housing": {
        "contract_end_date": "임대차 계약이 끝난 날짜를 알려주세요.",
        "deposit_amount": "보증금은 얼마인지 알려주세요.",
        "return_request": "임대인에게 보증금 반환을 요청했는지 알려주세요.",
    },
    "labor": {
        "resignation_date": "퇴사한 날짜를 알려주세요.",
        "employment_period": "계속 근무한 기간을 알려주세요.",
        "payment_request": "회사에 퇴직금 지급을 요청했는지 알려주세요.",
    },
    "consumer": {
        "payment_method": "어떤 방식으로 결제했는지 알려주세요.",
        "delivery_status": "물건을 실제로 받았는지 알려주세요.",
        "contact_history": "판매자 또는 카드사에 문의했는지 알려주세요.",
    },
}

FIELD_KEYWORDS = {
    "housing": {
        "contract_end_date": (
            "202",
            "계약 만료일",
            "종료일",
            "지난달",
            "이번 달",
        ),
        "deposit_amount": (
            "보증금",
            "만원",
            "원",
        ),
        "return_request": (
            "반환 요청",
            "돌려달라고",
            "내용증명",
            "문자",
            "요구",
        ),
    },
    "labor": {
        "resignation_date": (
            "퇴사일",
            "퇴직일",
            "사직일",
            "202",
            "지난달",
        ),
        "employment_period": (
            "근무 기간",
            "재직 기간",
            "개월",
            "년간",
            "입사",
        ),
        "payment_request": (
            "지급 요청",
            "달라고",
            "요구",
            "문자",
            "이메일",
        ),
    },
    "consumer": {
        "payment_method": (
            "카드",
            "계좌이체",
            "현금",
            "일시불",
            "할부",
        ),
        "delivery_status": (
            "받지 못",
            "미배송",
            "배송되지",
            "수령",
            "도착",
        ),
        "contact_history": (
            "카드사",
            "판매자",
            "문의",
            "연락",
            "고객센터",
        ),
    },
}

GENERAL_LEGAL_SEARCH_KEYWORDS = (
    "법 조문",
    "조문",
    "관련 법",
    "법률",
    "지급 기한",
    "기한을 알려",
)


def is_general_legal_search(question: str) -> bool:
    normalized_question = question.lower()

    return any(
        keyword in normalized_question
        for keyword in GENERAL_LEGAL_SEARCH_KEYWORDS
    )


def find_missing_fields(
    category: str,
    question: str,
) -> list[str]:
    if category not in FIELD_KEYWORDS:
        raise ValueError("지원하지 않는 카테고리입니다.")

    normalized_question = question.lower()
    missing_fields = []

    for field_name, keywords in FIELD_KEYWORDS[category].items():
        is_found = any(
            keyword.lower() in normalized_question
            for keyword in keywords
        )

        if not is_found:
            missing_fields.append(field_name)

    return missing_fields

class IntakeAgent:
    def assess(
        self,
        category: str,
        question: str,
        ) -> IntakeResult:
        if is_general_legal_search(question):
            return IntakeResult(
                is_ready_for_search=True,
            )

        missing_fields = find_missing_fields(
            category,
            question,
        )

        follow_up_questions = [
            FOLLOW_UP_QUESTIONS[category][field_name]
            for field_name in missing_fields
        ]

        return IntakeResult(
            is_ready_for_search=not missing_fields,
            missing_fields=missing_fields,
            follow_up_questions=follow_up_questions,
        )