from datetime import datetime, timedelta


ROLE_USERS = {
    "GUEST": {"id": "guest-demo", "role": "GUEST", "display_name": "비회원"},
    "USER": {"id": "user-demo", "role": "USER", "display_name": "법률초보"},
    "ADMIN": {"id": "admin-demo", "role": "ADMIN", "display_name": "관리자"},
}

MOCK_FAQ_ARTICLES = [
    {"id": "faq-1", "category": "housing", "question": "계약이 끝나면 보증금은 언제 반환하나요?", "answer": "계약 내용과 주택 인도 등 구체적인 사실관계를 확인해야 합니다.", "is_pinned": True, "is_active": True, "display_order": 1},
    {"id": "faq-2", "category": "housing", "question": "내용증명을 꼭 보내야 하나요?", "answer": "모든 경우에 필수는 아니지만 요청 사실을 남기는 방법으로 검토할 수 있습니다.", "is_pinned": False, "is_active": True, "display_order": 2},
    {"id": "faq-3", "category": "labor", "question": "퇴직금 요건은 무엇인가요?", "answer": "근로기간과 근로형태 등 구체적인 사실을 확인해야 합니다.", "is_pinned": True, "is_active": True, "display_order": 3},
    {"id": "faq-4", "category": "consumer", "question": "중고거래도 환불할 수 있나요?", "answer": "판매자 유형, 상품 설명과 실제 상태 등 사실관계에 따라 달라질 수 있습니다.", "is_pinned": False, "is_active": True, "display_order": 4},
]


def build_mock_questions() -> list[dict]:
    now = datetime.now().replace(microsecond=0)
    topics = [
        ("housing", "보증금 반환 요청은 어떻게 남기나요?"),
        ("labor", "퇴직금 계산에 어떤 자료가 필요한가요?"),
        ("consumer", "중고거래 미배송 자료를 어떻게 보관하나요?"),
    ]
    questions = []
    for index in range(23):
        category, title = topics[index % len(topics)]
        owner_id = "guest-demo" if index == 2 else f"seed-user-{index % 6}"
        created_at = now - timedelta(hours=index * 3)
        questions.append({
            "id": f"question-{1000 + index}",
            "owner_id": owner_id,
            "owner_role": "GUEST" if owner_id == "guest-demo" else "USER",
            "display_name": "비회원" if owner_id == "guest-demo" else f"사용자{index % 6 + 1}",
            "category": category,
            "title": title,
            "content": f"{title} 관련해서 준비해야 할 사항과 확인 순서가 궁금합니다. 개인정보가 없는 화면 확인용 질문입니다.",
            "visibility": "PUBLIC",
            "status": "ANSWERED" if index % 3 else "PENDING",
            "answer": None if index % 3 == 0 else "상황에 맞는 계약서, 대화 기록과 지급 내역을 먼저 정리해 보세요. 현재는 DEMO 답변입니다.",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
            "expires_at": (created_at + timedelta(days=7)).isoformat() if owner_id == "guest-demo" else None,
        })
    return questions
