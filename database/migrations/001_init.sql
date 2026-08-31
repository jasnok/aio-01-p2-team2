CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS legal_documents (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL CHECK (document_type IN ('LAW', 'CASE', 'GUIDELINE')),
    category TEXT NOT NULL CHECK (category IN ('housing', 'labor', 'consumer')),
    title TEXT NOT NULL,
    law_name TEXT,
    article_number TEXT,
    case_number TEXT,
    court TEXT,
    decided_at DATE,
    summary TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    effective_date DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_legal_documents_category_type
    ON legal_documents (category, document_type);

