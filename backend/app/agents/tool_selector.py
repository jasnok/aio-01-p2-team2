from app.agents.models import AgentProfile


RETRIEVAL_ORDER = (
    "search_cases",
    "search_legal_documents",
)

CONSUMER_RETRIEVAL_ORDER = (
    "search_laws",
    "search_consultations",
    "search_cases",
)


def select_tools(profile: AgentProfile, question: str) -> list[str]:
    # 소비자 질문은 법령·상담사례·판례를 각각 검색한다. 통합 검색으로
    # 대체하면 한 유형의 자료만 반환될 수 있기 때문이다.
    retrieval_order = (
        CONSUMER_RETRIEVAL_ORDER
        if profile.agent_id == "consumer"
        else RETRIEVAL_ORDER
    )
    return [
        tool_name
        for tool_name in retrieval_order
        if tool_name in profile.allowed_tools
    ]
