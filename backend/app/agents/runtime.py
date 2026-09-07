"""공통 Agent loop의 경계.

MVP 구현은 최대 4 step, 최대 3 tool call, Evidence-only 정책을 지켜야 합니다.
"""

from typing import Protocol

from backend.app.agents.models import AgentProfile, AgentState


class AgentRuntime(Protocol):
    def run(self, profile: AgentProfile, state: AgentState) -> AgentState: ...
