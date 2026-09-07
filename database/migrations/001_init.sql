CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS legal_documents (
    id BIGSERIAL PRIMARY KEY,

    external_id VARCHAR(200) NOT NULL,
    document_type VARCHAR(30) NOT NULL
        CHECK (
            document_type IN (
                'LAW',
                'CASE',
                'GUIDELINE',
                'ADMIN_DECISION',
                'CONSULTATION'
            )
        ),
    category VARCHAR(20) NOT NULL
        CHECK (category IN ('housing', 'labor', 'consumer')),

    title TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,

    law_name TEXT,
    article_number VARCHAR(100),

    case_number VARCHAR(150),
    case_name TEXT,
    court VARCHAR(150),
    decided_at DATE,
    judgment_result TEXT,

    source_name TEXT NOT NULL,
    source_url TEXT,
    source_type VARCHAR(20) NOT NULL
        CHECK (source_type IN ('file', 'api', 'seed')),
    raw_file TEXT,

    effective_date DATE,
    source_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    content_hash VARCHAR(64) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source_name, external_id)
);

CREATE TABLE IF NOT EXISTS legal_chunks (
    id BIGSERIAL PRIMARY KEY,

    document_id BIGINT NOT NULL
        REFERENCES legal_documents(id) ON DELETE CASCADE,

    chunk_index INTEGER NOT NULL,
    section_type VARCHAR(30),
    content TEXT NOT NULL,
    token_count INTEGER,

    embedding VECTOR(1536),
    embedding_model VARCHAR(100),
    embedding_version VARCHAR(50),

    content_hash VARCHAR(64) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGSERIAL PRIMARY KEY,

    source_name VARCHAR(150) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'RUNNING',
                'SUCCESS',
                'PARTIAL',
                'FAILED'
            )
        ),

    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,

    error_message TEXT
);