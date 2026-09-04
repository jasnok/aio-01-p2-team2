from backend.app.agents.models import AgentProfile


def ensure_tool_allowed(profile: AgentProfile, tool_name: str) -> None:
    if tool_name not in profile.allowed_tools:
        raise ValueError(f"허용되지 않은 Tool입니다: {tool_name}")
