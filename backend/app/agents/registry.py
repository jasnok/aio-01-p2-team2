from backend.app.agents.models import AgentProfile
from backend.app.agents.profiles import CONSUMER_AGENT, HOUSING_AGENT, LABOR_AGENT

AGENT_REGISTRY = {
    "housing": HOUSING_AGENT,
    "labor": LABOR_AGENT,
    "consumer": CONSUMER_AGENT,
    "secondhand": CONSUMER_AGENT,
}


def get_agent_profile(category: str) -> AgentProfile:
    try:
        return AGENT_REGISTRY[category]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 category입니다: {category}") from error
