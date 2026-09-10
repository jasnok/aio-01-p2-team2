from __future__ import annotations

import json
from typing import Any

import asyncpg

from backend.app.db.pool import get_db_pool


class SavedConversationNotFoundError(LookupError):
    pass


class SavedConversationRepository:
    """Uses the DB team's existing saved_* tables without schema changes."""

    async def save_analysis(
        self,
        *,
        user_id: int,
        category: str,
        question: str,
        result: dict[str, Any],
        execution_key: str,
    ) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                conversation = await connection.fetchrow(
                    """
                    INSERT INTO saved_conversations
                        (user_id, title, source_request_id, category, save_state, saved_at, updated_at)
                    VALUES ($1, $2, $3, $4, 'selected', NOW(), NOW())
                    ON CONFLICT (source_request_id)
                    DO UPDATE SET updated_at = NOW(), save_state = 'selected', saved_at = NOW()
                    RETURNING id, user_id
                    """,
                    user_id,
                    question[:100],
                    execution_key,
                    category,
                )
                if int(conversation["user_id"]) != user_id:
                    raise SavedConversationNotFoundError(execution_key)
                conversation_id = int(conversation["id"])
                await connection.execute(
                    """
                    INSERT INTO saved_messages
                        (conversation_id, role, content, execution_key, processing_status, snapshot)
                    VALUES ($1, 'user', $2, $3, 'completed', $4::jsonb)
                    ON CONFLICT (execution_key, role)
                    DO NOTHING
                    """,
                    conversation_id,
                    question,
                    execution_key,
                    self._snapshot({"kind": "legal_analysis", "question": question}),
                )
                assistant_id = await connection.fetchval(
                    """
                    INSERT INTO saved_messages
                        (conversation_id, role, content, execution_key, processing_status, snapshot)
                    VALUES ($1, 'assistant', $2, $3, 'completed', $4::jsonb)
                    ON CONFLICT (execution_key, role)
                    DO UPDATE SET content = EXCLUDED.content,
                                  processing_status = EXCLUDED.processing_status,
                                  snapshot = EXCLUDED.snapshot
                    RETURNING id
                    """,
                    conversation_id,
                    result.get("answer", ""),
                    execution_key,
                    self._snapshot(result),
                )
                await self._save_sources(connection, int(assistant_id), result)
                return conversation_id

    async def save_term_chat(
        self,
        *,
        user_id: int,
        question: str,
        answer: str,
        execution_key: str,
        conversation_id: int | None = None,
    ) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                if conversation_id is None:
                    conversation = await connection.fetchrow(
                        """
                        INSERT INTO saved_conversations
                            (user_id, title, source_request_id, category, save_state, saved_at, updated_at)
                        VALUES ($1, $2, $3, 'legal_terms', 'selected', NOW(), NOW())
                        ON CONFLICT (source_request_id)
                        DO UPDATE SET updated_at = NOW(), save_state = 'selected', saved_at = NOW()
                        RETURNING id, user_id
                        """,
                        user_id, question[:100], execution_key,
                    )
                else:
                    conversation = await connection.fetchrow(
                        """
                        UPDATE saved_conversations
                        SET updated_at = NOW(), save_state = 'selected', saved_at = NOW()
                        WHERE id = $1 AND user_id = $2 AND category = 'legal_terms'
                        RETURNING id, user_id
                        """,
                        conversation_id, user_id,
                    )
                if conversation is None or int(conversation["user_id"]) != user_id:
                    raise SavedConversationNotFoundError(conversation_id or execution_key)
                saved_id = int(conversation["id"])
                await connection.execute(
                    """
                    INSERT INTO saved_messages
                        (conversation_id, role, content, execution_key, processing_status, snapshot)
                    VALUES ($1, 'user', $2, $3, 'completed', $4::jsonb)
                    ON CONFLICT (execution_key, role) DO NOTHING
                    """,
                    saved_id, question, execution_key,
                    self._snapshot({"kind": "legal_term_chat", "question": question}),
                )
                await connection.execute(
                    """
                    INSERT INTO saved_messages
                        (conversation_id, role, content, execution_key, processing_status, snapshot)
                    VALUES ($1, 'assistant', $2, $3, 'completed', $4::jsonb)
                    ON CONFLICT (execution_key, role)
                    DO UPDATE SET content = EXCLUDED.content, snapshot = EXCLUDED.snapshot,
                                  processing_status = EXCLUDED.processing_status
                    """,
                    saved_id, answer, execution_key,
                    self._snapshot({"kind": "legal_term_chat", "answer": answer}),
                )
                return saved_id

    async def _save_sources(
        self,
        connection: asyncpg.Connection,
        message_id: int,
        result: dict[str, Any],
    ) -> None:
        for evidence in [
            *result.get("related_laws", []),
            *result.get("similar_cases", []),
            *result.get("consultations", []),
        ]:
            source_url = (evidence.get("source") or {}).get("url")
            if not source_url:
                continue
            metadata = evidence.get("metadata") or {}
            await connection.execute(
                """
                INSERT INTO saved_message_sources (message_id, document_id, chunk_id, source_url)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (message_id, document_id, chunk_id, source_url)
                DO NOTHING
                """,
                message_id,
                self._as_int(evidence.get("document_id")),
                self._as_int(metadata.get("chunk_id")),
                source_url,
            )

    async def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT id, title, category, save_state, saved_at, created_at, updated_at
                FROM saved_conversations
                WHERE user_id = $1
                ORDER BY updated_at DESC, id DESC
                """,
                user_id,
            )
        return [dict(row) for row in rows]

    async def list_history_page(
        self, *, user_id: int, page: int, page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        pool = await get_db_pool()
        offset = (page - 1) * page_size
        async with pool.acquire() as connection:
            total = await connection.fetchval(
                "SELECT COUNT(*) FROM saved_conversations WHERE user_id = $1", user_id,
            )
            rows = await connection.fetch(
                """
                SELECT c.id, c.title, c.category, c.created_at, c.updated_at,
                       first_user.content AS question,
                       last_answer.content AS answer,
                       last_answer.snapshot AS assistant_snapshot
                FROM saved_conversations c
                LEFT JOIN LATERAL (
                    SELECT content FROM saved_messages
                    WHERE conversation_id = c.id AND role = 'user'
                    ORDER BY id ASC LIMIT 1
                ) first_user ON TRUE
                LEFT JOIN LATERAL (
                    SELECT content, snapshot FROM saved_messages
                    WHERE conversation_id = c.id AND role = 'assistant'
                    ORDER BY id DESC LIMIT 1
                ) last_answer ON TRUE
                WHERE c.user_id = $1
                ORDER BY c.updated_at DESC, c.id DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, page_size, offset,
            )
        return [dict(row) for row in rows], int(total)

    async def restore(self, user_id: int, conversation_id: int) -> dict[str, Any]:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            conversation = await connection.fetchrow(
                """
                SELECT id, title, category, save_state, saved_at, created_at, updated_at
                FROM saved_conversations
                WHERE id = $1 AND user_id = $2
                """,
                conversation_id,
                user_id,
            )
            if conversation is None:
                raise SavedConversationNotFoundError(conversation_id)
            messages = await connection.fetch(
                """
                SELECT id, role, content, execution_key, processing_status, snapshot, created_at
                FROM saved_messages
                WHERE conversation_id = $1
                ORDER BY id ASC
                """,
                conversation_id,
            )
        return {"conversation": dict(conversation), "messages": [dict(row) for row in messages]}

    async def delete(self, user_id: int, conversation_id: int) -> None:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            status = await connection.execute(
                "DELETE FROM saved_conversations WHERE id = $1 AND user_id = $2",
                conversation_id,
                user_id,
            )
        if status != "DELETE 1":
            raise SavedConversationNotFoundError(conversation_id)

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _snapshot(payload: dict[str, Any]) -> str:
        """Matches saved_messages_storage_check in the shared DB contract."""
        return json.dumps(
            {"version": 1, "payload": payload},
            ensure_ascii=False,
            default=str,
        )
