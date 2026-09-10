from backend.app.db.pool import get_db_pool


class ConversationRepository:
    async def ping(self) -> bool:
        
        pool = await get_db_pool()

        value = await pool.fetchval("SELECT 1")
        return value == 1

    async def get_or_create_user_id(self, actor_key: str) -> int:
        pool = await get_db_pool()

        query = """
            INSERT INTO users (anonymous_key)
            VALUES ($1)
            ON CONFLICT (anonymous_key)
            DO UPDATE SET updated_at = NOW()
            RETURNING id
        """

        return await pool.fetchval(query, actor_key)

    async def create_conversation(
        self,
        *,
        user_id: int,
        title: str,
        source_request_id: str,
    ) -> dict:
        pool = await get_db_pool()

        query = """
            INSERT INTO saved_conversations (
                user_id,
                title,
                source_request_id
            )
            VALUES ($1, $2, $3)
            ON CONFLICT (source_request_id)
            DO UPDATE SET updated_at = saved_conversations.updated_at
            RETURNING id, user_id, title, source_request_id, created_at
        """

        row = await pool.fetchrow(
            query,
            user_id,
            title,
            source_request_id,
        )

        return dict(row)

    async def create_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
    ) -> dict:
        if role not in {"user", "assistant"}:
            raise ValueError("role은 user 또는 assistant만 가능합니다.")

        pool = await get_db_pool()

        query = """
            INSERT INTO saved_messages (
                conversation_id,
                role,
                content
            )
            VALUES ($1, $2, $3)
            RETURNING id, conversation_id, role, content, created_at
        """

        row = await pool.fetchrow(
            query,
            conversation_id,
            role,
            content,
        )

        return dict(row)

    async def create_message_source(
        self,
        *,
        message_id: int,
        document_id: int | None,
        chunk_id: int | None,
        source_url: str,
    ) -> dict | None:
        pool = await get_db_pool()

        query = """
            INSERT INTO saved_message_sources (
                message_id,
                document_id,
                chunk_id,
                source_url
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (message_id, document_id, chunk_id)
            DO NOTHING
            RETURNING id, message_id, document_id, chunk_id, source_url, created_at
        """

        row = await pool.fetchrow(
            query,
            message_id,
            document_id,
            chunk_id,
            source_url,
        )

        return dict(row) if row else None

    async def get_recent_messages(
        self,
        *,
        conversation_id: int,
        user_id: int,
        limit: int = 3,
    ) -> list[dict]:
        pool = await get_db_pool()

        query = """
            SELECT id, role, content, created_at
            FROM (
                SELECT
                    message.id,
                    message.role,
                    message.content,
                    message.created_at
                FROM saved_messages AS message
                JOIN saved_conversations AS conversation
                    ON conversation.id = message.conversation_id
                WHERE message.conversation_id = $1
                  AND conversation.user_id = $2
                ORDER BY message.created_at DESC, message.id DESC
                LIMIT $3
            ) AS recent_messages
            ORDER BY created_at ASC, id ASC
        """

        rows = await pool.fetch(
            query,
            conversation_id,
            user_id,
            limit,
        )

        return [dict(row) for row in rows]

    async def get_first_user_message(
        self,
        *,
        conversation_id: int,
        user_id: int,
    ) -> dict | None:
        pool = await get_db_pool()

        query = """
            SELECT
                message.id,
                message.role,
                message.content,
                message.created_at
            FROM saved_messages AS message
            JOIN saved_conversations AS conversation
                ON conversation.id = message.conversation_id
            WHERE message.conversation_id = $1
              AND conversation.user_id = $2
              AND message.role = 'user'
            ORDER BY message.created_at ASC, message.id ASC
            LIMIT 1
        """

        row = await pool.fetchrow(
            query,
            conversation_id,
            user_id,
        )

        return dict(row) if row else None

    async def get_conversation_for_user(
        self,
        *,
        conversation_id: int,
        user_id: int,
    ) -> dict | None:
        pool = await get_db_pool()

        query = """
            SELECT
                id,
                user_id,
                title,
                source_request_id,
                created_at,
                updated_at
            FROM saved_conversations
            WHERE id = $1
              AND user_id = $2
        """

        row = await pool.fetchrow(
            query,
            conversation_id,
            user_id,
        )

        return dict(row) if row else None

    async def find_user_id(
        self,
        *,
        actor_key: str,
    ) -> int | None:
        pool = await get_db_pool()

        query = """
            SELECT id
            FROM users
            WHERE anonymous_key = $1
        """

        return await pool.fetchval(query, actor_key)