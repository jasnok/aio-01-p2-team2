"""정규화된 법령을 조문 단위 pgvector Chunk로 변환합니다.

한 법령 전체를 하나의 벡터로 만들지 않고 실제 조문 하나를 Chunk 하나로
사용하여 사용자 질문과 직접 관련된 조문이 검색되게 합니다.
"""

from __future__ import annotations

import hashlib
import os

from database.ingestion.models import LegalChunk, NormalizedStatute


def build_statute_chunks(statute: NormalizedStatute) -> list[LegalChunk]:
    """법령명·조문번호·제목·본문을 포함한 검색 Chunk를 만듭니다."""
    chunks: list[LegalChunk] = []
    law_name = statute.document.law_name or statute.document.title
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    version = os.getenv("EMBEDDING_VERSION", "v1")

    for chunk_index, article in enumerate(statute.articles):
        parts = [f"법령명: {law_name}", f"조문: {article.article_number}"]
        if article.article_title:
            parts.append(f"조문 제목: {article.article_title}")
        parts.append(f"내용: {article.content}")
        content = "\n".join(parts)

        chunks.append(
            LegalChunk(
                chunk_index=chunk_index,
                section_type="article",
                content=content,
                # tiktoken을 도입하지 않았으므로 추정값을 넣지 않습니다.
                token_count=None,
                content_hash=hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
                embedding_model=model,
                embedding_version=version,
            )
        )

    if not chunks:
        raise ValueError(f"생성된 법령 Chunk가 없습니다: {law_name}")
    return chunks
