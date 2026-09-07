"""검색 속도를 위한 SQL"""

CREATE INDEX IF NOT EXISTS idx_legal_documents_category_type
    ON legal_documents (category, document_type);

CREATE INDEX IF NOT EXISTS idx_legal_documents_law_article
    ON legal_documents (law_name, article_number);

CREATE INDEX IF NOT EXISTS idx_legal_documents_case_number
    ON legal_documents (case_number);

CREATE INDEX IF NOT EXISTS idx_legal_documents_content_fts
    ON legal_documents
    USING GIN (
        to_tsvector(
            'simple',
            COALESCE(title, '') || ' ' ||
            COALESCE(summary, '') || ' ' ||
            COALESCE(content, '')
        )
    );

CREATE INDEX IF NOT EXISTS idx_legal_chunks_embedding_hnsw
    ON legal_chunks
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;