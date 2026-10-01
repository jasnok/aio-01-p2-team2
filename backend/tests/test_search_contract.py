import asyncio
from types import SimpleNamespace

import pytest

from backend.app.agents import runtime
from backend.app.agents.models import AgentState
from backend.app.agents.profiles import LABOR_AGENT
from backend.app.agents.search_contract import SearchContractError, search_evidence
from backend.app.mcp_clients.mcp_client import _result_payload


def item(kind="case"):
    return {"evidence_id": "id", "document_id": "id", "title": "title", "content": "content",
            "source": {"source_id": "source", "title": "title", "source_type": kind, "url": ""},
            "metadata": {"extension": [1, 2]}}


@pytest.mark.parametrize("payload", [None, [], {}, {"data": []},
    {"success": "true", "data": []}, {"success": 1, "data": []},
    {"success": True}, {"success": True, "data": None},
    {"success": True, "data": {}}, {"success": True, "data": ""},
    {"success": True, "data": [None]}, {"success": True, "data": [{}]},
    {"success": True, "data": [item("law")]}])
def test_single_search_rejects_malformed_result_before_completion(monkeypatch, payload):
    async def fake(*args, **kwargs):
        return payload
    monkeypatch.setattr(runtime, "search_cases", fake)
    state = AgentState(request_id="test", agent_id="labor", question="synthetic")
    with pytest.raises(SearchContractError):
        asyncio.run(runtime.LegalAgentRuntime().run_single_tool(LABOR_AGENT, state, "search_cases", 3))
    assert state.status != "completed"
    assert not any(event["stage"] == "tool_completed" for event in state.trace)


@pytest.mark.parametrize("data", [None, [], {}, {"items": None}, {"items": {}},
    {"items": [None]}, {"items": [item("consultation")]}])
def test_integrated_search_rejects_malformed_data(data):
    with pytest.raises(SearchContractError):
        search_evidence({"success": True, "data": data}, "search_legal_documents")


@pytest.mark.parametrize("tool, data", [("search_cases", []), ("search_laws", []),
    ("search_consultations", []), ("search_legal_documents", {"items": []})])
def test_real_empty_array_is_valid(tool, data):
    assert search_evidence({"success": True, "data": data}, tool) == []


@pytest.mark.parametrize("tool, kind", [("search_cases", "case"), ("search_laws", "law"),
    ("search_consultations", "consultation"), ("search_legal_documents", "law"),
    ("search_legal_documents", "case")])
def test_valid_evidence_and_extension_metadata_are_preserved(tool, kind):
    evidence = [item(kind)]
    data = {"items": evidence} if tool == "search_legal_documents" else evidence
    assert search_evidence({"success": True, "data": data}, tool) is evidence


def test_failed_search_does_not_include_external_error_text():
    with pytest.raises(RuntimeError) as caught:
        search_evidence({"success": False, "error": {"message": "synthetic-private-marker"}}, "search_cases")
    assert "synthetic-private-marker" not in str(caught.value)


def test_contract_failure_cancels_parallel_sibling_before_invalid_progress(monkeypatch):
    async def scenario():
        started, closed = asyncio.Event(), asyncio.Event()
        events = []
        async def malformed(*args, **kwargs):
            await started.wait()
            return {"success": True, "data": {}}
        async def slow(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()
        async def record(event):
            events.append(event)
        monkeypatch.setattr(runtime, "search_cases", malformed)
        monkeypatch.setattr(runtime, "search_legal_documents", slow)
        with pytest.raises(SearchContractError):
            await runtime.LegalAgentRuntime().run(LABOR_AGENT,
                AgentState(request_id="test", agent_id="labor", question="synthetic"), record)
        assert closed.is_set()
        assert all(event["stage"] != "tool_completed" for event in events)
    asyncio.run(scenario())


@pytest.mark.parametrize("structured, text", [(None, ""), (None, "[]"),
    (None, "not-json"), ([], '{"success": true}'), ("text", "{}")])
def test_transport_rejects_empty_non_json_and_non_object_result(structured, text):
    result = SimpleNamespace(isError=False, structuredContent=structured, content=[SimpleNamespace(text=text)])
    with pytest.raises(ValueError):
        _result_payload(result)


def test_structured_empty_object_is_not_replaced_by_text():
    result = SimpleNamespace(isError=False, structuredContent={}, content=[SimpleNamespace(text='{"success":true}')])
    assert _result_payload(result) == {}
    with pytest.raises(SearchContractError):
        search_evidence(_result_payload(result), "search_cases")


def test_transport_failure_hides_external_text():
    result = SimpleNamespace(isError=True, structuredContent=None,
        content=[SimpleNamespace(text="synthetic-private-marker")])
    with pytest.raises(RuntimeError) as caught:
        _result_payload(result)
    assert "synthetic-private-marker" not in str(caught.value)
