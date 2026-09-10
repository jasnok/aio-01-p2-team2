"""실제 소비자원 사례 검색 스크립트"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector import Vector
from pgvector.psycopg import register_vector


# ------------------------------------------------------------
# 프로젝트 경로 설정
# ------------------------------------------------------------

# 현재 파일:
# database/scripts/search_consumer.py
#
# parents[2]:
# 프로젝트 최상위 aio-01-p2-team2 폴더
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# database 패키지를 import할 수 있도록 프로젝트 루트를 추가합니다.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ------------------------------------------------------------
# 명령행 입력 설정
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="소비자원 피해구제 사례 유사도 검색"
    )

    # PowerShell에서 --query 뒤에 입력한 질문입니다.
    parser.add_argument(
        "--query",
        required=True,
        help="검색할 소비자 질문",
    )

    # 반환할 검색 결과 개수입니다.
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="반환할 결과 수",
    )

    return parser.parse_args()


# ------------------------------------------------------------
# 질문 Embedding 생성
# ------------------------------------------------------------

def create_query_embedding(
    query: str,
) -> list[float]:
    """
    사용자 질문을 text-embedding-3-small로 변환합니다.

    DB에 저장한 문서 Embedding과 질문 Embedding은
    반드시 같은 모델과 차원을 사용해야 합니다.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다."
        )

    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    expected_dimension = int(
        os.getenv(
            "EMBEDDING_DIMENSION",
            "1536",
        )
    )

    client = OpenAI(api_key=api_key)

    response = client.embeddings.create(
        model=embedding_model,
        input=query,
    )

    embedding = response.data[0].embedding

    # 모델이나 DB 설정이 잘못된 경우 검색 전에 중단합니다.
    if len(embedding) != expected_dimension:
        raise RuntimeError(
            "질문 Embedding 차원이 올바르지 않습니다. "
            f"expected={expected_dimension}, "
            f"actual={len(embedding)}"
        )

    return embedding


# ------------------------------------------------------------
# pgvector 검색
# ------------------------------------------------------------

def search_consumer_cases(
    database_url: str,
    query_embedding: list[float],
    top_k: int,
) -> list[tuple]:
    """
    consumer + CONSULTATION 문서에서
    cosine similarity가 높은 순서로 검색합니다.
    """

    search_sql = """
        SELECT
            d.id,
            d.external_id,
            d.title,
            d.document_type,
            d.source_name,
            d.source_url,

            -- cosine distance를 사람이 보기 쉬운 유사도로 변환합니다.
            -- 값이 클수록 질문과 의미가 가깝습니다.
            1 - (c.embedding <=> %s) AS similarity

        FROM legal_chunks c

        JOIN legal_documents d
            ON d.id = c.document_id

        WHERE d.category = 'consumer'
          AND d.document_type = 'CONSULTATION'
          AND c.embedding IS NOT NULL

        -- cosine distance는 값이 작을수록 유사합니다.
        ORDER BY c.embedding <=> %s

        LIMIT %s
    """

    with psycopg.connect(database_url) as connection:
        # psycopg에서 pgvector 값을 처리할 수 있도록 등록합니다.
        register_vector(connection)

        # Python list를 PostgreSQL vector 값으로 변환합니다.
        vector = Vector(query_embedding)

        with connection.cursor() as cursor:
            cursor.execute(
                search_sql,
                (
                    vector,
                    vector,
                    top_k,
                ),
            )

            return cursor.fetchall()


# ------------------------------------------------------------
# 실행
# ------------------------------------------------------------

def main() -> int:
    args = parse_args()

    # 프로젝트 공통 .env를 먼저 읽습니다.
    load_dotenv(PROJECT_ROOT / ".env")

    # DB 담당자용 환경설정이 있으면 이 값으로 덮어씁니다.
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL이 설정되지 않았습니다."
        )

    if args.top_k < 1:
        raise ValueError(
            "--top-k는 1 이상이어야 합니다."
        )

    print(f"검색 질문: {args.query}")
    print("질문 Embedding을 생성합니다.")

    query_embedding = create_query_embedding(
        args.query
    )

    print(
        f"질문 Embedding 차원: "
        f"{len(query_embedding)}"
    )

    results = search_consumer_cases(
        database_url=database_url,
        query_embedding=query_embedding,
        top_k=args.top_k,
    )

    if not results:
        print("검색 결과가 없습니다.")
        print(
            "consumer 문서와 Embedding이 "
            "DB에 있는지 확인하세요."
        )

        return 0

    print()
    print(f"검색 결과: {len(results)}건")
    print("=" * 70)

    for rank, result in enumerate(
        results,
        start=1,
    ):
        (
            document_id,
            external_id,
            title,
            document_type,
            source_name,
            source_url,
            similarity,
        ) = result

        print(f"[{rank}위]")
        print(f"문서 ID: {document_id}")
        print(f"외부 ID: {external_id}")
        print(f"문서 유형: {document_type}")
        print(f"제목: {title}")

        # 유사도는 검색 유사도이지 승소 가능성이 아닙니다.
        print(f"유사도: {float(similarity):.4f}")

        print(f"출처: {source_name}")
        print(f"원문: {source_url}")
        print("-" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())