"""노동위원회 판정사례를 Chunk로 변환합니다."""

from __future__ import annotations

import hashlib

from database.ingestion.models import (
    LegalChunk,
    NormalizedLegalDocument,
)


def build_labor_decision_chunk(
    document: NormalizedLegalDocument,
) -> LegalChunk:
    """
    원본 CSV에는 판정문 전체가 없으므로 사례 한 건을
    Chunk 하나로 유지합니다.
    """

    content_hash = hashlib.sha256(
        document.content.encode("utf-8")
    ).hexdigest()

    return LegalChunk(
        chunk_index=0,
        section_type="decision_summary",
        content=document.content,
        token_count=None,
        content_hash=content_hash,
        embedding_model="text-embedding-3-small",
        embedding_version="v1",
    )