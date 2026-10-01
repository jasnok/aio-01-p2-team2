import asyncio
import os

import pytest

from backend.app.repositories import saved_conversation_repository as module
from backend.app.services.saved_conversation_service import SavedConversationService
from scripts.benchmark_saved_context import create_tables, repository_for_connection


@pytest.mark.skipif(not os.getenv("RUN_POSTGRES_INTEGRATION"), reason="requires explicit PostgreSQL test URL")
def test_real_postgres_bounded_context_matches_full_history_and_checks_owner(monkeypatch):
    import asyncpg

    async def verify():
        connection = await asyncpg.connect(os.environ["RUN_POSTGRES_INTEGRATION"])
        try:
            await create_tables(connection)
            monkeypatch.setattr(module, "get_db_pool", repository_for_connection(connection))
            repository = module.SavedConversationRepository()
            service = SavedConversationService(repository)
            cases = [[], ["user"], ["assistant"], ["assistant", "user"],
                     ["assistant", "assistant", "assistant", "user"],
                     ["user", "assistant", "user", "assistant"], ["assistant"] * 8,
                     ["user", "assistant"] * 500]
            for roles in cases:
                await connection.execute("TRUNCATE saved_messages")
                await connection.executemany("""
                    INSERT INTO saved_messages(id, conversation_id, role, content, snapshot)
                    VALUES ($1,1,$2,$3,'{"payload": "excluded"}')
                """, [(index + 1, role, "duplicate" if index % 3 == 0 else f"message-{index}")
                      for index, role in enumerate(roles)])
                full = await repository.restore(42, 1)
                bounded = await repository.restore_context(42, 1)
                assert len(full["messages"]) == len(roles)
                assert len(bounded["messages"]) <= 4
                assert all(set(item) == {"id", "role", "content"} for item in bounded["messages"])
                for limit in (0, 1, 12, 3000):
                    expected = service._context_from_messages(full["messages"], limit)
                    assert await service.build_context_for_actor(
                        actor={"id": 42, "role": "USER"}, conversation_id=1, max_characters=limit) == expected
                    assert await service.build_term_context_for_actor(
                        actor={"id": 42, "role": "USER"}, conversation_id=1, max_characters=limit) == expected
            with pytest.raises(module.SavedConversationNotFoundError):
                await repository.restore_context(99, 1)
            with pytest.raises(module.SavedConversationNotFoundError):
                await repository.restore_context(42, 999)
            await connection.execute("UPDATE saved_conversations SET category='housing'")
            with pytest.raises(module.SavedConversationNotFoundError):
                await service.build_term_context_for_actor(actor={"id": 42, "role": "USER"}, conversation_id=1)
        finally:
            await connection.close()

    asyncio.run(verify())
