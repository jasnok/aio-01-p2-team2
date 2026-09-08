"""
OPENAI_API_KEY 없음
→ Embedding 실행 금지

Embedding 데이터 적재
→ text-embedding-3-small

MCP 질문 Embedding
→ 동일한 text-embedding-3-small
"""


from __future__ import annotations

import os

from openai import OpenAI


def create_embeddings(
    contents: list[str],
) -> list[list[float]]:
    """
    여러 Chunk 본문을 OpenAI Embedding으로 변환합니다.

    실제 OPENAI_API_KEY는 .env에만 저장하고
    코드나 .env.example에는 입력하지 않습니다.
    """

    model = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    expected_dimension = int(
        os.getenv(
            "EMBEDDING_DIMENSION",
            "1536",
        )
    )

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    response = client.embeddings.create(
        model=model,
        input=contents,
    )

    embeddings = [
        item.embedding
        for item in response.data
    ]

    # 설정 오류나 모델 변경을 조기에 발견합니다.
    for index, embedding in enumerate(embeddings):
        if len(embedding) != expected_dimension:
            raise ValueError(
                f"{index}번 Embedding 차원이 "
                f"{expected_dimension}이 아닙니다: "
                f"{len(embedding)}"
            )

    return embeddings