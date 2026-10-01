import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from backend.app.services import agent_run_service, legal_term_chat_service, run_metrics
from backend.app.services.mock_store import store

MARKER = "synthetic-private-marker"


def test_metrics_allow_only_finite_numeric_contract(monkeypatch):
    messages = []
    monkeypatch.setattr(run_metrics.logger, "info", messages.append)
    diagnostics = {"total_ms": 123, "llm_calls": 2, "evidence_count": MARKER,
                   "intake_ms": True, "context_ms": float("nan"),
                   "retrieval_ms": -1, "generation_ms": float("inf"),
                   "semantic_review": {"claims": [{"reason": MARKER}]},
                   "validation_error": MARKER,
                   "model_calls": [{"model": MARKER, "error_type": MARKER}],
                   "llm_usage_total": {"input_tokens": 12, "output_tokens": MARKER},
                   "model_stage_ms": {"answer": 15, MARKER: 20},
                   "tool_timings_ms": {"search_laws": 8, MARKER: 9}}
    run_metrics.log_result("run-test", SimpleNamespace(generation_status="llm", diagnostics=diagnostics))
    payload = json.loads(messages[0])
    assert MARKER not in messages[0]
    assert payload["diagnostics"] == {"total_ms": 123, "llm_calls": 2,
        "llm_usage_total": {"input_tokens": 12}, "model_stage_ms": {"answer": 15},
        "tool_timings_ms": {"search_laws": 8}}
    assert diagnostics["semantic_review"]["claims"][0]["reason"] == MARKER


@pytest.mark.parametrize("stage, expected", [("validation_started", "validation"),
    ("tool_selected", "retrieval"), ("generation_started", "generation")])
def test_analysis_failure_logs_stage_without_exception_payload(monkeypatch, caplog, stage, expected):
    run, _ = agent_run_service.create_run({"id": "log-owner", "role": "GUEST"},
        "housing", MARKER, "log-test", cache_enabled=False)
    async def snapshot(_):
        pass
    async def answer(request, event_callback):
        await event_callback({"stage": stage, "tool": "search_laws"})
        raise RuntimeError(MARKER)
    monkeypatch.setattr(agent_run_service, "save_snapshot", snapshot)
    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", answer)
    with caplog.at_level(logging.ERROR):
        try:
            asyncio.run(agent_run_service._execute_run(run["run_id"]))
            assert run["error"]["code"] == "ANALYSIS_FAILED"
        finally:
            store.agent_runs.pop(run["run_id"], None)
    assert MARKER not in caplog.text
    assert f"stage={expected} error_type=RuntimeError" in caplog.text
    assert run["run_id"] in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_term_generation_failure_hides_exception_text(monkeypatch, caplog):
    monkeypatch.setattr(legal_term_chat_service, "get_settings", lambda: SimpleNamespace(llm_provider="test"))
    monkeypatch.setattr(legal_term_chat_service, "get_provider", lambda _: object())
    async def fail(*args):
        raise RuntimeError(MARKER)
    monkeypatch.setattr(legal_term_chat_service, "structured_call", fail)
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="LLM_UNAVAILABLE"):
        asyncio.run(legal_term_chat_service.LegalTermChatService().chat(MARKER, []))
    assert MARKER not in caplog.text
    assert "stage=generation request_id=term-" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_search_failure_preserves_http_contract_without_logging_query(monkeypatch, caplog):
    from fastapi import HTTPException
    from backend.app.routers import legal
    async def fail(*args):
        raise RuntimeError(MARKER)
    monkeypatch.setattr(legal.LegalAgentRuntime, "run_single_tool", fail)
    with caplog.at_level(logging.ERROR), pytest.raises(HTTPException) as caught:
        asyncio.run(legal._search_by_tool(category="housing", query=MARKER, top_k=2,
            tool_name="search_laws", expected_source_type="law"))
    assert caught.value.status_code == 502
    assert caught.value.detail["code"] == "MCP_UNAVAILABLE"
    assert MARKER not in caplog.text
    assert "stage=retrieval" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_term_run_lookup_failure_does_not_log_user_supplied_path(monkeypatch, caplog):
    from fastapi import HTTPException
    from backend.app.routers import legal_terms
    async def fail(*args):
        raise RuntimeError(MARKER)
    monkeypatch.setattr(legal_terms.legal_term_runs, "get_for_actor", fail)
    with caplog.at_level(logging.ERROR), pytest.raises(HTTPException) as caught:
        asyncio.run(legal_terms.save_legal_term_run(MARKER, {"id": "user", "role": "USER"}))
    assert caught.value.status_code == 503
    assert MARKER not in caplog.text
    assert "request_id=unavailable error_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
