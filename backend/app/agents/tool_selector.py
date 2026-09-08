from backend.app.agents.models import AgentProfile


LAW_SEARCH_KEYWORDS = (
    "조문",
    "조항",
    "몇 조",
    "법률",
)


def select_tools(profile: AgentProfile, question: str) -> list[str]:
    normalized_question = question.strip()

    if profile.agent_id == "consumer":
        requested_tools = [
            "search_laws",
            "search_consultations",
            "search_cases",
        ]
    elif any(keyword in normalized_question for keyword in LAW_SEARCH_KEYWORDS):
        requested_tools = ["search_legal_documents", "search_cases"]
    else:
        requested_tools = ["search_cases", "search_legal_documents"]

    return [
        tool_name
        for tool_name in requested_tools
        if tool_name in profile.allowed_tools
    ]
