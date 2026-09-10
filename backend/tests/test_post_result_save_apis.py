import asyncio

import pytest

from backend.app.routers import legal_terms, mock_api
from backend.app.services import legal_term_run_store
from backend.app.services.legal_term_run_store import LegalTermRunForbiddenError, LegalTermRunStore


def memory_settings():
    return type("Settings", (), {"redis_enabled": False, "term_run_ttl_seconds": 3600})()


def test_legal_term_run_store_keeps_answer_server_side_and_checks_owner(monkeypatch) -> None:
    monkeypatch.setattr(legal_term_run_store, "get_settings", memory_settings)
    store = LegalTermRunStore()
    asyncio.run(store.remember(
        actor={"id": 42, "role": "USER"}, request_id="term-1",
        question="임금체불", answer="설명", conversation_id=None,
    ))

    result = asyncio.run(store.get_for_actor("term-1", {"id": 42, "role": "USER"}))
    assert result["answer"] == "설명"
    with pytest.raises(LegalTermRunForbiddenError):
        asyncio.run(store.get_for_actor("term-1", {"id": 99, "role": "USER"}))


def test_completed_agent_run_save_uses_verified_server_run(monkeypatch) -> None:
    run = {
        "run_id": "run-1", "status": "completed", "category": "labor",
        "question": "임금", "result": {"answer": "답변"},
    }
    called = {}

    async def save_run(actor, saved_run):
        called["actor"] = actor
        called["run"] = saved_run
        return 55

    monkeypatch.setattr(mock_api, "get_run_for_save", lambda run_id, actor: run)
    monkeypatch.setattr(mock_api.saved_conversation_service, "save_run", save_run)

    result = asyncio.run(mock_api.save_agent_run("run-1", {"id": 42, "role": "USER"}))
    assert result == {"conversation_id": 55, "saved": True}
    assert called["run"] is run


def test_legal_term_save_api_uses_cached_answer_not_frontend_payload(monkeypatch) -> None:
    class Store:
        async def get_for_actor(self, request_id, actor):
            assert request_id == "term-1"
            return {
                "request_id": "term-1", "question": "임금체불",
                "answer": "저장할 서버 답변", "conversation_id": None,
            }

    captured = {}

    async def save_term_chat(**kwargs):
        captured.update(kwargs)
        return 77

    monkeypatch.setattr(legal_terms, "legal_term_runs", Store())
    monkeypatch.setattr(legal_terms.saved_conversation_service, "save_term_chat", save_term_chat)

    result = asyncio.run(legal_terms.save_legal_term_run("term-1", {"id": 42, "role": "USER"}))
    assert result == {"conversation_id": 77, "saved": True}
    assert captured["answer"] == "저장할 서버 답변"
