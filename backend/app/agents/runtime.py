"""공통 Agent loop의 경계.

MVP 구현은 최대 4 step, 최대 3 tool call,
Evidence-only 정책을 지켜야 합니다.
"""

from typing import Protocol

from backend.app.agents.models import AgentProfile, AgentState
from backend.app.agents.tool_selector import select_tools
from backend.app.mcp_clients.legal_mcp import (
    search_cases,
    search_legal_documents,
)
from backend.app.policies.tool_policy import ensure_tool_allowed


class AgentRuntime(Protocol):
    async def run(
        self,
        profile: AgentProfile,
        state: AgentState,
    ) -> tuple[AgentState, list[dict]]: ...


class LegalAgentRuntime:
    """하나의 공통 Runtime이며, 분야 차이는 Profile로만 구분한다."""

    async def run(
        self,
        profile: AgentProfile,
        state: AgentState,
    ) -> tuple[AgentState, list[dict]]:
        if profile.agent_id not in {"labor", "housing", "consumer"}:
            raise ValueError("지원하지 않는 Agent Profile입니다.")

        selected_tools = select_tools(profile, state.question)

        if not selected_tools:
            raise ValueError("실행할 수 있는 MCP Tool이 없습니다.")

        if len(selected_tools) > 3:
            raise ValueError("MVP의 최대 Tool 호출 횟수를 초과했습니다.")

        all_evidence = []

        for tool_name in selected_tools:
            ensure_tool_allowed(profile, tool_name)

            state.current_step += 1
            state.trace.append(
                {
                    "stage": "tool_selected",
                    "tool": tool_name,
                    "category": profile.agent_id,
                }
            )

            if tool_name == "search_cases":
                payload = await search_cases(
                    state.question,
                    profile.agent_id,
                    top_k=3,
                )

            elif tool_name == "search_legal_documents":
                payload = await search_legal_documents(
                    state.question,
                    profile.agent_id,
                    top_k=3,
                )

            else:
                raise ValueError(f"지원하지 않는 Tool입니다: {tool_name}")

            state.tool_calls += 1

            if not payload.get("success", True):
                error = payload.get("error") or {}

                raise RuntimeError(
                    payload.get("message")
                    or error.get("message")
                    or payload.get("error_code")
                    or error.get("code")
                    or "MCP 검색에 실패했습니다."
                )

            if tool_name == "search_cases":
                evidence = payload.get("data") or []

            else:
                data = payload.get("data") or {}
                evidence = data.get("items", [])

            if not isinstance(evidence, list):
                raise ValueError(
                    f"MCP {tool_name} 결과 형식이 올바르지 않습니다."
                )

            all_evidence.extend(evidence)

            state.trace.append(
                {
                    "stage": "tool_completed",
                    "tool": tool_name,
                    "result_count": len(evidence),
                }
            )

        state.evidence_count = len(all_evidence)
        state.status = "completed"
        state.termination_reason = (
            "model_finished" if all_evidence else "no_results"
        )

        return state, all_evidence