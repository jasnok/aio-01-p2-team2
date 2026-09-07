"""공통 Agent loop의 경계.

MVP 구현은 최대 4 step, 최대 3 tool call, Evidence-only 정책을 지켜야 합니다.
"""

from typing import Protocol

from backend.app.agents.models import AgentProfile, AgentState
from backend.app.mcp_clients.legal_mcp import search_cases
from backend.app.policies.tool_policy import ensure_tool_allowed


class AgentRuntime(Protocol):
    async def run(self, profile: AgentProfile, state: AgentState) -> tuple[AgentState, list[dict]]: ...


class LegalAgentRuntime:
    """하나의 공통 Runtime이며, 분야 차이는 Profile로만 구분한다."""

    async def run(self, profile: AgentProfile, state: AgentState) -> tuple[AgentState, list[dict]]:
        if profile.agent_id != "labor":
            raise ValueError("실제 MCP 연결은 labor Profile부터 지원합니다.")
        ensure_tool_allowed(profile, "search_cases")
        state.current_step = 1
        state.trace.append({"stage": "tool_selected", "tool": "search_cases", "category": profile.agent_id})
        payload = await search_cases(state.question, profile.agent_id, top_k=3)
        state.tool_calls += 1
        if not payload.get("success", True):
            raise RuntimeError(payload.get("message") or payload.get("error_code") or "MCP 검색에 실패했습니다.")
        evidence = payload.get("data") or []
        if not isinstance(evidence, list):
            raise ValueError("MCP search_cases 결과 형식이 올바르지 않습니다.")
        state.evidence_count = len(evidence)
        state.trace.append({"stage": "tool_completed", "tool": "search_cases", "result_count": len(evidence)})
        state.current_step = 2
        state.status = "completed"
        state.termination_reason = "model_finished" if evidence else "no_results"
        return state, evidence
