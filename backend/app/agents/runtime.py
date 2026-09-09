"""공통 Agent loop의 경계.

MVP 구현은 최대 4 step, 최대 3 tool call,
Evidence-only 정책을 지켜야 합니다.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agents.models import AgentProfile, AgentState
from app.agents.tool_selector import is_comprehensive_search, select_tools
from app.mcp_clients.legal_mcp import (
    search_cases,
    search_consultations,
    search_laws,
    search_legal_documents,
    search_laws,
)
from app.policies.tool_policy import ensure_tool_allowed


TARGET_EVIDENCE_COUNT = 3
MAX_TOOL_CALLS = 3


class AgentRuntime(Protocol):
    async def run(
        self,
        profile: AgentProfile,
        state: AgentState,
        event_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> tuple[AgentState, list[dict]]: ...


class LegalAgentRuntime:
    """하나의 공통 Runtime이며, 분야 차이는 Profile로만 구분한다."""

    async def run(
        self,
        profile: AgentProfile,
        state: AgentState,
        event_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> tuple[AgentState, list[dict]]:
        if profile.agent_id not in {"labor", "housing", "consumer"}:
            raise ValueError("지원하지 않는 Agent Profile입니다.")

        selected_tools = select_tools(profile, state.question)
        comprehensive_search = is_comprehensive_search(state.question)

        if not selected_tools:
            raise ValueError("실행할 수 있는 MCP Tool이 없습니다.")

        if len(selected_tools) > MAX_TOOL_CALLS:
            raise ValueError("MVP의 최대 Tool 호출 횟수를 초과했습니다.")

        all_evidence = []
        evidence_keys: set[str] = set()

        for tool_name in selected_tools:
            # 법령 → 판례 → 문서 검색 순서를 끝까지 실행한다.
            # 검색 결과 수가 충분하더라도 모든 검색 근거를 확보한다.

            ensure_tool_allowed(profile, tool_name)

            state.current_step += 1
            state.trace.append(
                {
                    "stage": "tool_selected",
                    "tool": tool_name,
                    "category": profile.agent_id,
                }
            )
            if event_callback:
                await event_callback(state.trace[-1])

            if tool_name == "search_laws":
                payload = await search_laws(
                    state.question,
                    profile.agent_id,
                    top_k=3,
                )

            elif tool_name == "search_cases":
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

            elif tool_name == "search_consultations":
                payload = await search_consultations(
                    state.question,
                    profile.agent_id,
                    top_k=3,
                )

            elif tool_name == "search_laws":
                payload = await search_laws(
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

            if tool_name in {
                "search_cases",
                "search_consultations",
                "search_laws",
            }:
                evidence = payload.get("data") or []

            else:
                data = payload.get("data") or {}
                evidence = data.get("items", [])

            if not isinstance(evidence, list):
                raise ValueError(
                    f"MCP {tool_name} 결과 형식이 올바르지 않습니다."
                )

            new_evidence = []
            for item in evidence:
                evidence_key = str(
                    item.get("evidence_id")
                    or item.get("document_id")
                    or repr(item)
                )
                if evidence_key not in evidence_keys:
                    evidence_keys.add(evidence_key)
                    new_evidence.append(item)

            all_evidence.extend(new_evidence)

            state.trace.append(
                {
                    "stage": "tool_completed",
                    "tool": tool_name,
                    "result_count": len(new_evidence),
                }
            )
            if event_callback:
                await event_callback(state.trace[-1])

            if len(all_evidence) < TARGET_EVIDENCE_COUNT:
                state.trace.append(
                    {
                        "stage": "evidence_insufficient",
                        "evidence_count": len(all_evidence),
                        "target_count": TARGET_EVIDENCE_COUNT,
                    }
                )

        state.evidence_count = len(all_evidence)
        state.status = "completed"
        if not all_evidence:
            state.termination_reason = "no_results"
        elif len(all_evidence) < TARGET_EVIDENCE_COUNT:
            state.termination_reason = "insufficient_evidence"
        else:
            state.termination_reason = "model_finished"

        return state, all_evidence

    async def run_single_tool(
        self,
        profile: AgentProfile,
        state: AgentState,
        tool_name: str,
        top_k: int,
    ) -> tuple[AgentState, list[dict]]:
        """독립 검색 API에서 지정한 자료 유형만 한 번 검색한다."""
        ensure_tool_allowed(profile, tool_name)
        state.current_step += 1
        state.trace.append(
            {"stage": "tool_selected", "tool": tool_name, "category": profile.agent_id}
        )

        if tool_name == "search_laws":
            payload = await search_laws(state.question, profile.agent_id, top_k=top_k)
        elif tool_name == "search_cases":
            payload = await search_cases(state.question, profile.agent_id, top_k=top_k)
        elif tool_name == "search_consultations":
            payload = await search_consultations(state.question, profile.agent_id, top_k=top_k)
        else:
            raise ValueError(f"독립 검색에서 지원하지 않는 Tool입니다: {tool_name}")

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

        evidence = payload.get("data") or []
        if not isinstance(evidence, list):
            raise ValueError(f"MCP {tool_name} 결과 형식이 올바르지 않습니다.")

        state.evidence_count = len(evidence)
        state.status = "completed"
        state.termination_reason = "model_finished" if evidence else "no_results"
        state.trace.append(
            {"stage": "tool_completed", "tool": tool_name, "result_count": len(evidence)}
        )
        return state, evidence
