from app.agents.models import AgentProfile


LAW_SEARCH_KEYWORDS = (
    "조문",
    "조항",
    "몇 조",
    "법률",
)

CASE_SEARCH_KEYWORDS = (
    "판례",
    "판결",
    "소송",
)

CONSULTATION_SEARCH_KEYWORDS = (
    "사례",
    "상담",
)

COMPREHENSIVE_SEARCH_KEYWORDS = (
    "모두",
    "전부",
    "통합",
    "함께",
)


def is_comprehensive_search(question: str) -> bool:
    """법령·판례·사례를 함께 요청한 질문인지 판별한다."""
    normalized_question = question.strip()
    has_search_target = any(
        keyword in normalized_question
        for keyword in (
            *LAW_SEARCH_KEYWORDS,
            *CASE_SEARCH_KEYWORDS,
            *CONSULTATION_SEARCH_KEYWORDS,
        )
    )
    return has_search_target and any(
        keyword in normalized_question
        for keyword in COMPREHENSIVE_SEARCH_KEYWORDS
    )


def select_tools(profile: AgentProfile, question: str) -> list[str]:
    normalized_question = question.strip()

    if is_comprehensive_search(normalized_question):
        # Agent별 권한 필터를 거치므로, 상담 사례가 없는 노동·주거 분야는
        # 법령과 판례만 조회한다.
        requested_tools = [
            "search_laws",
            "search_cases",
            "search_consultations",
        ]
    elif profile.agent_id == "consumer":
        if any(keyword in normalized_question for keyword in LAW_SEARCH_KEYWORDS):
            requested_tools = [
                "search_laws",
                "search_consultations",
                "search_cases",
            ]
        else:
            requested_tools = [
                "search_consultations",
                "search_cases",
                "search_legal_documents",
            ]
    elif any(keyword in normalized_question for keyword in LAW_SEARCH_KEYWORDS):
        requested_tools = ["search_laws", "search_cases"]
    else:
        requested_tools = ["search_cases", "search_legal_documents"]

    return [
        tool_name
        for tool_name in requested_tools
        if tool_name in profile.allowed_tools
    ]
