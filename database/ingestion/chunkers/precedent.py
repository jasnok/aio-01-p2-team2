"""
정규화된 판례를 pgvector 검색용 Chunk로 변환합니다.
판시사항과 판결요지는 대체로 각각 하나의 Chunk가 되고, 긴 판례 전문은 여러 Chunk로 나뉩니다.
"""

from __future__ import annotations

import hashlib
import os
import re

from database.ingestion.models import (
    LegalChunk,
    NormalizedPrecedent,
)


MAX_CHUNK_CHARACTERS = 2400
OVERLAP_CHARACTERS = 250


def split_long_text(
    text: str,
    max_characters: int = MAX_CHUNK_CHARACTERS,
    overlap: int = OVERLAP_CHARACTERS,
) -> list[str]:
    """
    긴 판례내용을 문장 경계를 우선하여 나눕니다.

    한국어 토큰 계산기를 별도로 사용하지 않으므로
    MVP에서는 글자 수 기준으로 분할합니다.
    """

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_characters:
        return [text]

    sentences = re.split(
        r"(?<=[.!?다요])\s+|\n+",
        text,
    )

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        candidate = (
            f"{current} {sentence}".strip()
            if current
            else sentence
        )

        if (
            len(candidate) <= max_characters
            or not current
        ):
            current = candidate
            continue

        chunks.append(current)

        overlap_text = current[-overlap:]
        current = f"{overlap_text} {sentence}".strip()

    if current:
        chunks.append(current)

    return chunks


def build_precedent_chunks(
    precedent: NormalizedPrecedent,
) -> list[LegalChunk]:
    """판례의 의미 단위별 검색 Chunk를 생성합니다."""

    model = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    version = os.getenv(
        "EMBEDDING_VERSION",
        "v1",
    )

    document = precedent.document
    chunks: list[LegalChunk] = []

    for section in precedent.sections:
        split_contents = split_long_text(
            section.content
        )

        for split_content in split_contents:
            content = "\n".join(
                [
                    f"사건명: {document.case_name}",
                    f"사건번호: {document.case_number}",
                    f"법원: {document.court or ''}",
                    f"선고일: {document.decided_at or ''}",
                    f"구분: {section.title}",
                    f"내용: {split_content}",
                ]
            )

            chunks.append(
                LegalChunk(
                    chunk_index=len(chunks),
                    section_type=section.section_type,
                    content=content,
                    token_count=None,
                    content_hash=hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                    embedding_model=model,
                    embedding_version=version,
                )
            )

    if not chunks:
        raise ValueError(
            f"판례 Chunk가 없습니다: {document.title}"
        )

    return chunks