# 소비자 피해구제 사례는 개별 질문과 답변이 하나의 의미 단위이므로 처음에는 사례 하나를 Chunk 하나로 사용하면 됩니다.
from __future__ import annotations

import hashlib

from database.ingestion.models import (
    LegalChunk,
    NormalizedLegalDocument,
)


def build_consumer_relief_chunk(
    document: NormalizedLegalDocument,
) -> LegalChunk:
    """
    소비자 피해구제 사례 하나를 Chunk 하나로 변환합니다.

    질문과 답변을 분리하면 답변 근거가 질문과 떨어질 수 있으므로
    MVP에서는 제목·품목·질문·답변 전체를 한 Chunk로 유지합니다.
    """

    content = document.content

    content_hash = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    return LegalChunk(
        chunk_index=0,
        section_type="question_answer",
        content=content,

        # 현재 tiktoken을 사용하지 않으므로 비워둡니다.
        # 나중에 실제 토큰 계산을 추가할 수 있습니다.
        token_count=None,

        content_hash=content_hash,
        embedding_model="text-embedding-3-small",
        embedding_version="v1",
    )