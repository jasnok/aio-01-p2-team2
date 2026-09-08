"""
기본 실행
→ 정규화 결과만 화면에서 확인
→ DB 변경 없음

--load-db
→ 문서와 Chunk를 DB에 적재
→ Embedding 없음

--load-db --with-embeddings
→ 문서, Chunk, Embedding 모두 적재

RAG data 만드는
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb


# 스크립트를 어느 경로에서 실행하더라도
# 프로젝트 패키지를 import할 수 있도록 루트를 추가합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.chunkers.consumer_relief import (
    build_consumer_relief_chunk,
)
from database.ingestion.normalizers.consumer_relief import (
    normalize_consumer_relief_xml,
)


XML_PATH = (
    PROJECT_ROOT
    / "database"
    / "raw"
    / "files"
    / "consumer"
    / "한국소비자원_품목별 피해구제 사례_20220331.xml"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="소비자원 피해구제 사례 적재"
    )

    # 최초에는 --limit 5를 사용합니다.
    # 전체 적재 시에는 --limit을 생략합니다.
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    # 이 옵션이 없으면 절대로 DB를 변경하지 않습니다.
    parser.add_argument(
        "--load-db",
        action="store_true",
    )

    # 이 옵션이 있으면 OpenAI API를 호출합니다.
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # 실제 비밀번호와 API Key가 있는 로컬 파일입니다.
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    documents = list(
        normalize_consumer_relief_xml(
            XML_PATH,
            limit=args.limit,
        )
    )

    chunks = [
        build_consumer_relief_chunk(document)
        for document in documents
    ]

    print(f"정규화 문서 수: {len(documents)}")

    # --load-db가 없으면 미리보기만 하고 종료합니다.
    if not args.load_db:
        first = documents[0]

        print(f"첫 번째 ID: {first.external_id}")
        print(f"첫 번째 제목: {first.title}")
        print("DB는 변경하지 않았습니다.")

        return 0

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )

    # Embedding 옵션이 없으면 null 벡터를 사용합니다.
    embeddings: list[list[float] | None]

    if args.with_embeddings:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY가 없습니다."
            )

        client = OpenAI(api_key=api_key)

        batch_size = 50
        embeddings = []

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[
                    chunk.content
                    for chunk in batch
                ],
            )

            embeddings.extend(
                item.embedding
                for item in response.data
            )

            print(
                f"Embedding 진행: "
                f"{min(start + batch_size, len(chunks))}/{len(chunks)}"
            )
    else:
        embeddings = [None] * len(chunks)

    with psycopg.connect(database_url) as connection:
        # Python list를 pgvector 타입으로 저장할 수 있게 등록합니다.
        register_vector(connection)

        with connection.cursor() as cursor:
            for document, chunk, embedding in zip(
                documents,
                chunks,
                embeddings,
                strict=True,
            ):
                # 동일 source_name + external_id가 있으면 갱신합니다.
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        external_id,
                        document_type,
                        category,
                        title,
                        summary,
                        content,
                        source_name,
                        source_url,
                        source_type,
                        raw_file,
                        content_hash,
                        metadata
                    )
                    VALUES (
                        %(external_id)s,
                        %(document_type)s,
                        %(category)s,
                        %(title)s,
                        %(summary)s,
                        %(content)s,
                        %(source_name)s,
                        %(source_url)s,
                        %(source_type)s,
                        %(raw_file)s,
                        %(content_hash)s,
                        %(metadata)s
                    )
                    ON CONFLICT (
                        source_name,
                        external_id
                    )
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content = EXCLUDED.content,
                        source_url = EXCLUDED.source_url,
                        raw_file = EXCLUDED.raw_file,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    WHERE
                        legal_documents.content_hash
                        IS DISTINCT FROM
                        EXCLUDED.content_hash
                    RETURNING id
                    """,
                    {
                        "external_id": document.external_id,
                        "document_type": document.document_type,
                        "category": document.category,
                        "title": document.title,
                        "summary": document.summary,
                        "content": document.content,
                        "source_name": document.source_name,
                        "source_url": document.source_url,
                        "source_type": document.source_type,
                        "raw_file": document.raw_file,
                        "content_hash": document.content_hash,
                        "metadata": Jsonb(document.metadata),
                    },
                )

                result = cursor.fetchone()

                # content_hash가 같으면 RETURNING 결과가 없습니다.
                # 기존 문서 ID를 다시 가져옵니다.
                if result is None:
                    cursor.execute(
                        """
                        SELECT id
                        FROM legal_documents
                        WHERE source_name = %s
                          AND external_id = %s
                        """,
                        (
                            document.source_name,
                            document.external_id,
                        ),
                    )

                    document_id = cursor.fetchone()[0]
                else:
                    document_id = result[0]

                    # 본문이 변경된 경우 기존 Chunk를 제거합니다.
                    cursor.execute(
                        """
                        DELETE FROM legal_chunks
                        WHERE document_id = %s
                        """,
                        (document_id,),
                    )

                cursor.execute(
                    """
                    INSERT INTO legal_chunks (
                        document_id,
                        chunk_index,
                        section_type,
                        content,
                        token_count,
                        embedding,
                        embedding_model,
                        embedding_version,
                        content_hash
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (
                        document_id,
                        chunk_index
                    )
                    DO NOTHING
                    """,
                    (
                        document_id,
                        chunk.chunk_index,
                        chunk.section_type,
                        chunk.content,
                        chunk.token_count,
                        embedding,
                        chunk.embedding_model,
                        chunk.embedding_version,
                        chunk.content_hash,
                    ),
                )

        # 모든 문서와 Chunk가 성공한 경우에만 저장합니다.
        connection.commit()

    print(f"DB 적재 문서 수: {len(documents)}")
    print(
        "Embedding 생성 수: "
        f"{sum(value is not None for value in embeddings)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())