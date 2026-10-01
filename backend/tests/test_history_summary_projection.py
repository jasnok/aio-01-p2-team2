import asyncio
import json
import os

import pytest

from backend.app.repositories import saved_conversation_repository as module
from backend.app.services.saved_conversation_service import SavedConversationService
from scripts.benchmark_history_projection import full_snapshot_page
from scripts.benchmark_saved_context import create_tables, repository_for_connection


@pytest.mark.skipif(not os.getenv("RUN_POSTGRES_INTEGRATION"), reason="requires explicit PostgreSQL test URL")
def test_real_postgres_history_projection_preserves_public_summary_and_details(monkeypatch):
    import asyncpg

    async def verify():
        connection = await asyncpg.connect(os.environ["RUN_POSTGRES_INTEGRATION"])
        try:
            await create_tables(connection)
            monkeypatch.setattr(module, "get_db_pool", repository_for_connection(connection))
            repository = module.SavedConversationRepository()
            snapshots = [None, {}, {"payload": None}, {"payload": []}, {"payload": "legacy"},
                         {"payload": {"question_summary": "summary", "unused_evidence": "x" * 65536}},
                         {"payload": {"question_summary": "", "answer": "fallback"}},
                         {"payload": {"question_summary": False, "answer": None}},
                         {"payload": {"question_summary": {"nested": "legacy"}}},
                         {"payload": {"answer": "a" * 400}}]
            for category in ("housing", "legal_terms"):
                await connection.execute("UPDATE saved_conversations SET category=$1", category)
                for snapshot in snapshots:
                    await connection.execute("TRUNCATE saved_messages")
                    await connection.execute("""
                        INSERT INTO saved_messages(id,conversation_id,role,content,snapshot)
                        VALUES (1,1,'user','question',NULL),(2,1,'assistant','answer fallback',$1::jsonb)
                    """, json.dumps(snapshot) if snapshot is not None else None)
                    full, total = await full_snapshot_page(connection)
                    projected, projected_total = await repository.list_history_page(user_id=42, page=1, page_size=20)
                    assert projected_total == total == 1
                    assert [SavedConversationService._history_item(row) for row in projected] == [
                        SavedConversationService._history_item(row) for row in full]
                    selected = SavedConversationService._snapshot_payload(projected[0]["assistant_snapshot"])
                    assert set(selected) == {"question_summary", "answer"}
                    restored = await repository.restore(42, 1)
                    raw = restored["messages"][1]["snapshot"]
                    assert (json.loads(raw) if raw else None) == snapshot
            await connection.execute("INSERT INTO saved_conversations SELECT 2,99,'other','housing','selected',NOW(),NOW(),NOW()")
            assert await repository.list_history_page(user_id=99, page=1, page_size=20) != ([], 0)
            rows, total = await repository.list_history_page(user_id=42, page=2, page_size=1)
            assert rows == [] and total == 1
            rows, _ = await repository.list_history_page(user_id=42, page=1, page_size=1)
            assert [row["id"] for row in rows] == [1]
            await connection.execute("TRUNCATE saved_messages")
            await connection.execute("UPDATE saved_conversations SET category='housing' WHERE id=1")
            rows, _ = await repository.list_history_page(user_id=42, page=1, page_size=20)
            assert SavedConversationService._history_item(rows[0])["summary"] == ""
            await connection.execute("""
                INSERT INTO saved_conversations
                SELECT i,42,'new','housing','selected',NOW(),NOW(),NOW()
                FROM generate_series(3,4) i
            """)
            rows, total = await repository.list_history_page(user_id=42, page=1, page_size=2)
            assert total == 3 and [row["id"] for row in rows] == [4, 3]
            rows, total = await repository.list_history_page(user_id=42, page=2, page_size=2)
            assert total == 3 and [row["id"] for row in rows] == [1]
        finally:
            await connection.close()

    asyncio.run(verify())
