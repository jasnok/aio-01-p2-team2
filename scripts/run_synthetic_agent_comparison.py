"""Run a deterministic 100-case synthetic comparison against the local checkout.

The script exercises LegalAgentRuntime with in-process fake MCP responses only.
It never calls an external LLM, database, or MCP server.  Its JSON output is
intended for the agent test report, not as a claim about production quality.
"""

import asyncio
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.agents import runtime


CURRENT_EXPECTED_TOOLS = {
    "housing": ["search_cases", "search_legal_documents"],
    "labor": ["search_cases", "search_legal_documents"],
    "consumer": ["search_laws", "search_consultations", "search_cases"],
}


def build_cases():
    groups = [
        ("normal", 45),
        ("no_results", 10),
        ("insufficient_evidence", 15),
        ("duplicate_evidence", 10),
        ("tool_failure", 10),
        ("invalid_payload", 5),
        ("over_limit", 5),
    ]
    categories = ("housing", "labor", "consumer")
    cases = []
    number = 1
    for group, amount in groups:
        for _ in range(amount):
            cases.append(
                {
                    "id": f"S{number:03d}",
                    "group": group,
                    "category": categories[(number - 1) % len(categories)],
                    "question": "보증금 반환과 계약 해지 관련 자료를 확인하고 싶습니다.",
                }
            )
            number += 1
    return cases


def payload_for(case, tool_name):
    group = case["group"]
    if group == "tool_failure":
        return {"success": False, "error": {"message": "synthetic MCP failure"}}
    if group == "invalid_payload":
        return {"success": True, "data": [] if tool_name == "search_legal_documents" else {"items": []}}
    if group == "no_results":
        items = []
    elif group == "insufficient_evidence":
        items = [{"evidence_id": f"{case['id']}-shared"}]
    elif group == "duplicate_evidence":
        items = [
            {"evidence_id": f"{case['id']}-a"},
            {"evidence_id": f"{case['id']}-b"},
        ]
    else:
        items = [
            {"evidence_id": f"{case['id']}-{tool_name}-{index}"}
            for index in range(1, 4)
        ]
    if tool_name == "search_legal_documents":
        return {"success": True, "data": {"items": items}}
    return {"success": True, "data": items}


def expected_outcome(case, state, evidence, error):
    group = case["group"]
    if group in {"tool_failure", "invalid_payload", "over_limit"}:
        return error is not None
    if error is not None:
        return False
    if group == "normal":
        return state.termination_reason == "model_finished" and len(evidence) >= 3
    if group == "no_results":
        return state.termination_reason == "no_results" and not evidence
    if group == "insufficient_evidence":
        return state.termination_reason == "insufficient_evidence" and len(evidence) == 1
    if group == "duplicate_evidence":
        return state.termination_reason == "insufficient_evidence" and len(evidence) == 2
    return False


async def run_case(case):
    profile = get_agent_profile(case["category"])
    state = AgentState(request_id=case["id"], agent_id=profile.agent_id, question=case["question"])
    selected = runtime.select_tools(profile, state.question)
    selection_checked = case["group"] != "over_limit"
    selection_ok = selected == CURRENT_EXPECTED_TOOLS[case["category"]] if selection_checked else None

    original_selector = runtime.select_tools
    originals = {
        name: getattr(runtime, name)
        for name in ("search_cases", "search_consultations", "search_legal_documents", "search_laws")
        if hasattr(runtime, name)
    }

    def make_search(name):
        async def search(*_args, **_kwargs):
            return payload_for(case, name)
        return search

    for name in originals:
        setattr(runtime, name, make_search(name))
    if case["group"] == "over_limit":
        runtime.select_tools = lambda *_args, **_kwargs: ["search_cases"] * 4

    evidence = []
    error = None
    try:
        state, evidence = await runtime.LegalAgentRuntime().run(profile, state)
    except Exception as exc:  # expected for synthetic failure cases
        error = type(exc).__name__
    finally:
        runtime.select_tools = original_selector
        for name, original in originals.items():
            setattr(runtime, name, original)

    passed = expected_outcome(case, state, evidence, error)
    return {
        **case,
        "selected_tools": selected,
        "selection_checked": selection_checked,
        "selection_ok": selection_ok,
        "passed": passed,
        "response_consistent": passed,
        "tool_calls": state.tool_calls,
        "termination_reason": state.termination_reason,
        "evidence_count": len(evidence),
        "error": error,
    }


def main():
    cases = build_cases()
    results = [asyncio.run(run_case(case)) for case in cases]
    selection_rows = [row for row in results if row["selection_checked"]]
    summary = {
        "suite": "synthetic_local_runtime_v1",
        "case_count": len(results),
        "group_counts": dict(Counter(row["group"] for row in results)),
        "task_completed": sum(row["passed"] for row in results),
        "tool_selection_correct": sum(row["selection_ok"] for row in selection_rows),
        "tool_selection_total": len(selection_rows),
        "response_consistent": sum(row["response_consistent"] for row in results),
        "average_same_tool_retries": 0.0,
        "note": "No same-tool retry exists in LegalAgentRuntime; different retrieval tools are tracked as tool calls, not retries.",
    }
    output = {"summary": summary, "results": results}
    path = Path("output") / "synthetic_agent_comparison.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
