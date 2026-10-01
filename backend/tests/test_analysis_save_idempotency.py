import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from backend.app.repositories import saved_conversation_repository
from backend.app.repositories.saved_conversation_repository import SavedConversationNotFoundError
from backend.app.schemas.legal import LegalQuestionResponse
from backend.app.services import agent_run_service
from backend.app.services.mock_store import store
from backend.app.services.saved_conversation_service import SavedConversationService


def response():
    return LegalQuestionResponse(
        request_id="req-synthetic", agent_id="housing", termination_reason="model_finished",
        question_summary="synthetic", answer="synthetic answer", is_mock=False)


async def execute_saved_run(monkeypatch, service):
    actor = {"id": 42, "role": "USER"}
    run, _ = agent_run_service.create_run(actor, "housing", "synthetic question", "synthetic",
                                          save_selected=True, cache_enabled=False)
    async def answer(*args, **kwargs):
        return response()
    async def snapshot(*args):
        pass
    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", answer)
    monkeypatch.setattr(agent_run_service, "save_snapshot", snapshot)
    monkeypatch.setattr(agent_run_service, "saved_conversation_service", service)
    monkeypatch.setattr(agent_run_service, "get_settings", lambda: SimpleNamespace(backend_mock_mode=False))
    monkeypatch.setattr(agent_run_service, "log_result", lambda *args: None)
    try:
        await agent_run_service._execute_run(run["run_id"])
        assert run["status"] == "completed"
        first = run["result"]["conversation_id"]
        assert await service.save_run(actor, run) == first
        assert await service.save_run(actor, run) == first
        return run
    finally:
        store.agent_runs.pop(run["run_id"], None)


def test_worker_auto_save_and_post_save_use_one_execution_key(monkeypatch):
    class Repository:
        keys = []
        async def save_analysis(self, **kwargs):
            self.keys.append(kwargs["execution_key"])
            return 71
    repository = Repository()
    run = asyncio.run(execute_saved_run(monkeypatch, SavedConversationService(repository)))
    assert repository.keys == [run["run_id"]] * 3
    assert run["result"]["request_id"] == "req-synthetic"


@pytest.mark.skipif(not os.getenv("RUN_POSTGRES_INTEGRATION"), reason="requires an explicit PostgreSQL test URL")
def test_real_postgres_auto_and_post_save_create_one_conversation(monkeypatch):
    import asyncpg

    async def verify():
        connection = await asyncpg.connect(os.environ["RUN_POSTGRES_INTEGRATION"])
        try:
            # Temporary tables and an exclusive search path prevent access to
            # application tables, even when using a local development DB.
            await connection.execute("SET search_path TO pg_temp")
            await connection.execute("""
                CREATE TEMP TABLE saved_conversations (
                    id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, title TEXT,
                    source_request_id TEXT UNIQUE NOT NULL, category TEXT,
                    save_state TEXT, saved_at TIMESTAMPTZ, updated_at TIMESTAMPTZ);
                CREATE TEMP TABLE saved_messages (
                    id SERIAL PRIMARY KEY, conversation_id INTEGER REFERENCES saved_conversations(id),
                    role TEXT, content TEXT, execution_key TEXT, processing_status TEXT, snapshot JSONB,
                    UNIQUE (execution_key, role));
            """)
            class Pool:
                @asynccontextmanager
                async def acquire(self):
                    yield connection
            async def pool():
                return Pool()
            monkeypatch.setattr(saved_conversation_repository, "get_db_pool", pool)
            service = SavedConversationService()
            run = await execute_saved_run(monkeypatch, service)
            assert await connection.fetchval("SELECT count(*) FROM saved_conversations") == 1
            assert await connection.fetchval("SELECT count(*) FROM saved_messages") == 2
            assert await connection.fetchval("SELECT source_request_id FROM saved_conversations") == run["run_id"]
            assert await connection.fetchval("SELECT content FROM saved_messages WHERE role='assistant'") == "synthetic answer"
            with pytest.raises(SavedConversationNotFoundError):
                await service.save_run({"id": 99, "role": "USER"}, run)
            assert await connection.fetchval("SELECT user_id FROM saved_conversations") == 42
            assert await connection.fetchval("SELECT count(*) FROM saved_messages") == 2
        finally:
            await connection.close()  # Drops only this connection's temporary tables.

    asyncio.run(verify())
