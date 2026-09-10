/*사용자가 명시적으로 저장한 대화만 PostgreSQL에 장기 보관할 때 필요*/

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    anonymous_key VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    source_request_id VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES saved_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL
        REFERENCES saved_messages(id) ON DELETE CASCADE,
    document_id BIGINT REFERENCES legal_documents(id),
    chunk_id BIGINT REFERENCES legal_chunks(id),
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE NULLS NOT DISTINCT (message_id, document_id, chunk_id)
);