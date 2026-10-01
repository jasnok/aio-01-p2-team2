"""공통 Agent loop의 경계.

MVP 구현은 최대 4 step, 최대 3 tool call,
Evidence-only 정책을 지켜야 합니다.
"""

import asyncio
from time import perf_counter
from collections.abc import Awaitable, Callable
from typing import Protocol

from backend.app.agents.models import AgentProfile, AgentState
from backend.app.agents.tool_selector import select_tools
from backend.app.agents.search_contract import search_evidence
from backend.app.mcp_clients.legal_mcp import (
    search_cases,
    search_consultations,
    search_legal_documents,
    search_laws,
)
from backend.app.policies.tool_policy import ensure_tool_allowed


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

        if not selected_tools:
            raise ValueError("실행할 수 있는 MCP Tool이 없습니다.")

        if len(selected_tools) > MAX_TOOL_CALLS:
            raise ValueError("MVP의 최대 Tool 호출 횟수를 초과했습니다.")

        # Check every tool before launching any request. All searches use the
        # same immutable question and do not depend on another tool's output.
        for tool_name in selected_tools:
            ensure_tool_allowed(profile, tool_name)
            state.current_step += 1
            state.trace.append({"stage": "tool_selected", "tool": tool_name,
                                "category": profile.agent_id})
            if event_callback:
                await event_callback(state.trace[-1])

        functions = {"search_cases": search_cases, "search_laws": search_laws,
                     "search_consultations": search_consultations,
                     "search_legal_documents": search_legal_documents}
        callback_lock = asyncio.Lock()

        async def search(tool_name):
            started = perf_counter()
            state.tool_calls += 1
            payload = await functions[tool_name](state.question, profile.agent_id, top_k=3)
            evidence = search_evidence(payload, tool_name)
            event = {"stage": "tool_completed", "tool": tool_name, "result_count": len(evidence),
                     "elapsed_ms": round((perf_counter() - started) * 1000), "evidence": evidence}
            # Serialize callbacks so parallel completions cannot overwrite a
            # newer Redis snapshot with an older one.
            async with callback_lock:
                state.trace.append(event)
                if event_callback:
                    await event_callback(event)
            return evidence

        tasks = [asyncio.create_task(search(tool)) for tool in selected_tools]
        try:
            batches = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        all_evidence = []
        evidence_keys: set[str] = set()
        # Completion order affects progress only. Result ordering remains
        # deterministic and respects the profile's tool order.
        for batch in batches:
            for item in batch:
                key = str(item.get("evidence_id") or item.get("document_id") or repr(item))
                if key not in evidence_keys:
                    evidence_keys.add(key)
                    all_evidence.append(item)

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
        evidence = search_evidence(payload, tool_name)

        state.evidence_count = len(evidence)
        state.status = "completed"
        state.termination_reason = "model_finished" if evidence else "no_results"
        state.trace.append(
            {"stage": "tool_completed", "tool": tool_name, "result_count": len(evidence)}
        )
        return state, evidence
