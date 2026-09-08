"""
소비자 카테고리의 법령·판례·피해구제 사례 통합 검색 테스트

검색 대상:
- LAW          : 법령
- CASE         : 판례
- CONSULTATION : 소비자원 피해구제 사례
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector import Vector
from pgvector.psycopg import register_vector


# ---------------------------------------------------------
# 프로젝트 경로 및 import 설정
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.ingestion.embedders.openai_embedder import (
    create_embeddings,
)


# ---------------------------------------------------------
# 실행 옵션
# ---------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="법령·판례·소비자 사례 통합 검색"
    )

    parser.add_argument(
        "--query",
        required=True,
        help="검색할 사용자 질문",
    )

    parser.add_argument(
        "--category",
        choices=("housing", "labor", "consumer"),
        default="consumer",
        help="검색 카테고리",
    )

    parser.add_argument(
        "--top-k-per-type",
        type=int,
        default=3,
        help="문서 유형별 반환 개수",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="최소 벡터 유사도",
    )

    return parser.parse_args()


# ---------------------------------------------------------
# 통합 벡터 검색
# ---------------------------------------------------------

def search_all(
    database_url: str,
    query_embedding: list[float],
    category: str,
    top_k_per_type: int,
    threshold: float,
) -> list[tuple]:

    search_sql = """
        WITH scored AS (
            SELECT
                d.id AS document_id,
                d.document_type,
                d.external_id,
                d.title,
                d.law_name,
                d.article_number,
                d.case_number,
                d.case_name,
                d.court,
                d.decided_at,
                d.source_name,
                d.source_url,
                c.id AS chunk_id,
                c.chunk_index,
                c.section_type,
                c.content,

                -- cosine distance를 유사도로 변환
                1 - (c.embedding <=> %(query_vector)s)
                    AS similarity

            FROM legal_documents d
            JOIN legal_chunks c
                ON c.document_id = d.id

            WHERE d.document_type IN (
                'LAW',
                'CASE',
                'CONSULTATION'
            )
              AND c.embedding IS NOT NULL
              AND (
                    d.category = %(category)s
                    OR d.metadata -> 'categories'
                        ? %(category)s
              )
        ),

        -- 같은 문서의 여러 Chunk 중 가장 높은 결과만 선택
        document_deduplicated AS (
            SELECT
                scored.*,
                ROW_NUMBER() OVER (
                    PARTITION BY document_id
                    ORDER BY
                        similarity DESC,
                        chunk_index ASC
                ) AS document_rank
            FROM scored
        ),

        -- LAW, CASE, CONSULTATION 유형별 순위 부여
        type_ranked AS (
            SELECT
                document_deduplicated.*,
                ROW_NUMBER() OVER (
                    PARTITION BY document_type
                    ORDER BY similarity DESC
                ) AS type_rank
            FROM document_deduplicated
            WHERE document_rank = 1
              AND similarity >= %(threshold)s
        )

        SELECT
            document_type,
            external_id,
            title,
            law_name,
            article_number,
            case_number,
            case_name,
            court,
            decided_at,
            chunk_index,
            section_type,
            content,
            similarity,
            source_name,
            source_url
        FROM type_ranked
        WHERE type_rank <= %(top_k_per_type)s

        -- 법령 → 판례 → 사례 순서로 출력
        ORDER BY
            CASE document_type
                WHEN 'LAW' THEN 1
                WHEN 'CASE' THEN 2
                WHEN 'CONSULTATION' THEN 3
                ELSE 4
            END,
            similarity DESC;
    """

    parameters = {
        "query_vector": Vector(query_embedding),
        "category": category,
        "top_k_per_type": top_k_per_type,
        "threshold": threshold,
    }

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(search_sql, parameters)
            return cursor.fetchall()


def get_type_name(document_type: str) -> str:
    return {
        "LAW": "법령",
        "CASE": "판례",
        "CONSULTATION": "피해구제 사례",
    }.get(document_type, document_type)


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------

def main() -> int:
    args = parse_args()

    # 프로젝트 공통 환경변수
    load_dotenv(PROJECT_ROOT / ".env")

    # DB 담당 환경변수가 있으면 우선 적용
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )

    if args.top_k_per_type < 1:
        raise ValueError(
            "--top-k-per-type은 1 이상이어야 합니다."
        )

    print(f"검색 질문: {args.query}")
    print(f"검색 카테고리: {args.category}")
    print("질문 Embedding 생성 중...")

    query_embedding = create_embeddings(
        [args.query]
    )[0]

    if len(query_embedding) != 1536:
        raise RuntimeError(
            "질문 Embedding이 1536차원이 아닙니다."
        )

    results = search_all(
        database_url=database_url,
        query_embedding=query_embedding,
        category=args.category,
        top_k_per_type=args.top_k_per_type,
        threshold=args.threshold,
    )

    if not results:
        print("검색 결과가 없습니다.")
        print("Embedding 적재 여부와 threshold를 확인하세요.")
        return 0

    current_type = None

    for row in results:
        (
            document_type,
            external_id,
            title,
            law_name,
            article_number,
            case_number,
            case_name,
            court,
            decided_at,
            chunk_index,
            section_type,
            content,
            similarity,
            source_name,
            source_url,
        ) = row

        if current_type != document_type:
            current_type = document_type
            print()
            print("=" * 80)
            print(f"[{get_type_name(document_type)} 검색 결과]")
            print("=" * 80)

        print(f"문서 ID: {external_id}")
        print(f"제목: {title}")

        if law_name:
            print(f"법령명: {law_name}")

        if article_number:
            print(f"조문: {article_number}")

        if case_number:
            print(f"사건번호: {case_number}")

        if case_name:
            print(f"사건명: {case_name}")

        if court:
            print(f"법원: {court}")

        if decided_at:
            print(f"선고일: {decided_at}")

        print(f"Chunk: {chunk_index}")
        print(f"구성 부분: {section_type}")
        print(f"유사도: {float(similarity):.4f}")
        print(f"내용: {content[:500]}")
        print(f"출처: {source_name}")
        print(f"원문: {source_url}")
        print("-" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())