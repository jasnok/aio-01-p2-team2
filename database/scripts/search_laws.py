"""
현행 법령 Hybrid Search 검증용 CLI입니다.

검색 순서:
1. category filter
2. document_type filter
3. keyword/exact search
4. vector search
5. score 결합
6. document 단위 중복 제거
7. relevance threshold
8. Top 3

실행 예시:

python scripts/search_laws.py `
  --query "계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다." `
  --category housing `
  --top-k 3

이 스크립트는 검색 품질 검증용이며 DB 데이터를 수정하지 않습니다.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector import Vector
from pgvector.psycopg import register_vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.embedders.openai_embedder import create_embeddings


# 사용자 표현과 법령 표현이 다른 경우를 보완하기 위한 동의어입니다.
# 대표 질문 검색 결과를 평가하면서 단어를 추가하거나 수정하면 됩니다.
LEGAL_SYNONYMS = {
    "housing": {
        "보증금": [
            "임대차보증금",
            "전세보증금",
            "보증금반환",
            "반환",
        ],
        "돌려주지": [
            "반환",
            "미반환",
            "채무불이행",
        ],
        "계약이 끝": [
            "임대차 종료",
            "임대차기간 만료",
            "기간 만료",
        ],
        "임대인": [
            "임대인",
            "임대차",
        ],
    },
    "labor": {
        "퇴직금": [
            "퇴직급여",
            "퇴직금 지급",
            "퇴직급여 지급",
        ],
        "받지 못": [
            "미지급",
            "체불",
            "지급의무",
        ],
        "지급하지": [
            "미지급",
            "체불",
            "지급기한",
        ],
        "해고": [
            "해고예고",
            "부당해고",
            "근로관계 종료",
        ],
    },
    "consumer": {
        "중고거래": [
            "매매",
            "매매계약",
            "전자상거래",
        ],
        "물건을 보내지": [
            "미배송",
            "배송",
            "채무불이행",
        ],
        "돈을 보냈": [
            "매매대금",
            "대금 지급",
            "대금",
        ],
        "판매자": [
            "매도인",
            "사업자",
        ],
        "사기": [
            "기망",
            "편취",
            "사기죄",
        ],
        "환불": [
            "청약철회",
            "대금 환급",
            "계약 해제",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    """PowerShell에서 전달받을 검색 조건을 정의합니다."""

    parser = argparse.ArgumentParser(
        description="현행 법령 Hybrid Search"
    )

    parser.add_argument(
        "--query",
        required=True,
        help="검색할 사용자 질문",
    )

    parser.add_argument(
        "--category",
        required=True,
        choices=("housing", "labor", "consumer"),
        help="검색할 법률 카테고리",
    )

    # MCP 명세상 최종 반환 결과는 최대 3건입니다.
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="반환할 법령 수. 1 이상 3 이하",
    )

    # 최종 계획서의 초기 Hybrid Search 가중치입니다.
    parser.add_argument(
        "--vector-weight",
        type=float,
        default=0.7,
        help="Vector Search 점수 가중치",
    )

    parser.add_argument(
        "--keyword-weight",
        type=float,
        default=0.3,
        help="Keyword Search 점수 가중치",
    )

    # 대표 질문 평가 결과에 따라 변경할 수 있습니다.
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.25,
        help="결과에 포함할Additionally, the query requests unified code file. Need continue code. Token budget okay. Ensure no 'download'. Continue.```python최소 결합 점수",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """검색 옵션이 허용 범위에 있는지 검사합니다."""

    if not args.query.strip():
        raise ValueError("--query는 빈 문자열일 수 없습니다.")

    if not 1 <= args.top_k <= 3:
        raise ValueError("--top-k는 1 이상 3 이하여야 합니다.")

    if args.vector_weight < 0 or args.keyword_weight < 0:
        raise ValueError("검색 가중치는 0 이상이어야 합니다.")

    weight_sum = args.vector_weight + args.keyword_weight

    if abs(weight_sum - 1.0) > 0.0001:
        raise ValueError(
            "--vector-weight와 --keyword-weight의 합은 "
            "1이어야 합니다."
        )

    if not 0 <= args.threshold <= 1:
        raise ValueError("--threshold는 0 이상 1 이하여야 합니다.")


def extract_keyword_tokens(query: str) -> list[str]:
    """
    사용자 질문에서 Keyword Search에 사용할 단어를 추출합니다.

    2글자 미만의 단어와 중복된 단어는 제거하고
    최대 10개까지 사용합니다.
    """

    tokens = re.findall(r"[가-힣A-Za-z0-9]+", query)

    filtered_tokens = [
        token
        for token in tokens
        if len(token) >= 2
    ]

    # 입력 순서를 유지하면서 중복을 제거합니다.
    return list(dict.fromkeys(filtered_tokens))[:10]


def expand_keyword_tokens(
    query: str,
    category: str,
) -> list[str]:
    """
    일반 사용자 표현을 법률 문서에서 사용하는 표현으로 확장합니다.

    예:
    돌려주지 않는다
    → 반환, 미반환, 채무불이행
    """

    tokens = extract_keyword_tokens(query)

    category_synonyms = LEGAL_SYNONYMS.get(category, {})

    for phrase, synonyms in category_synonyms.items():
        if phrase in query:
            tokens.extend(synonyms)

    # 동의어 추가 후 다시 중복을 제거합니다.
    return list(dict.fromkeys(tokens))


def search_laws(
    database_url: str,
    query: str,
    query_embedding: list[float],
    category: str,
    top_k: int,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    threshold: float = 0.25,
):
    """
    법령 Chunk를 Hybrid Search 방식으로 검색합니다.

    같은 법령에서 여러 조문이 검색되더라도 가장 점수가 높은
    조문 하나만 최종 결과에 포함합니다.
    """

    keywords = expand_keyword_tokens(
        query=query,
        category=category,
    )

    sql = """
        WITH filtered AS (
            /*
             * 1. category filter
             * 2. document_type filter
             *
             * 민법처럼 여러 카테고리에 공통으로 사용되는 법령은
             * metadata.categories도 함께 검사합니다.
             */
            SELECT
                d.id AS document_id,
                d.title,
                d.external_id,
                d.effective_date,
                d.law_name,
                d.article_number,
                d.source_name,
                d.source_url,
                c.chunk_index,
                c.content,
                c.embedding
            FROM legal_documents d
            JOIN legal_chunks c
              ON c.document_id = d.id
            WHERE d.document_type = 'LAW'
              AND c.embedding IS NOT NULL
              AND (
                  d.category = %(category)s
                  OR d.metadata -> 'categories' ? %(category)s
              )
        ),
        scored AS (
            /*
             * 3. keyword/exact search
             * 4. vector search
             */
            SELECT
                filtered.*,

                /*
                 * cosine distance를 similarity로 변환합니다.
                 * 값이 클수록 사용자 질문과 가깝습니다.
                 */
                1 - (
                    embedding <=> %(query_vector)s
                ) AS vector_score,

                /*
                 * Keyword 점수 계산:
                 *
                 * - 질문 전체가 문서에 포함되면 1점
                 * - 아니면 확장 Keyword가 포함된 비율을 사용
                 */
                GREATEST(
                    CASE
                        WHEN CONCAT_WS(
                            ' ',
                            title,
                            law_name,
                            article_number,
                            content
                        ) ILIKE
                            '%%' || %(query)s || '%%'
                        THEN 1.0
                        ELSE 0.0
                    END,

                    COALESCE(
                        (
                            SELECT COUNT(*)::double precision
                            FROM UNNEST(
                                %(keywords)s::text[]
                            ) AS keyword
                            WHERE CONCAT_WS(
                                ' ',
                                filtered.title,
                                filtered.law_name,
                                filtered.article_number,
                                filtered.content
                            ) ILIKE
                                '%%' || keyword || '%%'
                        )
                        /
                        NULLIF(
                            CARDINALITY(
                                %(keywords)s::text[]
                            ),
                            0
                        ),
                        0.0
                    )
                ) AS keyword_score
            FROM filtered
        ),
        combined AS (
            /*
             * 5. score 결합
             *
             * 초기 가중치:
             * Vector 0.7 + Keyword 0.3
             */
            SELECT
                scored.*,
                (
                    %(vector_weight)s * vector_score
                    +
                    %(keyword_weight)s * keyword_score
                ) AS combined_score
            FROM scored
        ),
        deduplicated AS (
            /*
             * 6. document 단위 중복 제거
             *
             * 같은 법령에서 여러 조문이 검색되면
             * 결합 점수가 가장 높은 조문 하나만 선택합니다.
             */
            SELECT
                combined.*,

                ROW_NUMBER() OVER (
                    PARTITION BY document_id
                    ORDER BY
                        combined_score DESC,
                        vector_score DESC,
                        chunk_index ASC
                ) AS document_rank
            FROM combined
        )
        SELECT
            title,
            external_id,
            effective_date,
            chunk_index,
            content,
            source_name,
            source_url,
            vector_score,
            keyword_score,
            combined_score
        FROM deduplicated
        WHERE document_rank = 1

          /* 7. relevance threshold */
          AND combined_score >= %(threshold)s

        ORDER BY
            combined_score DESC,
            vector_score DESC

        /* 8. Top 3 */
        LIMIT %(top_k)s
    """

    parameters = {
        "query": query,
        "keywords": keywords,
        "query_vector": Vector(query_embedding),
        "category": category,
        "vector_weight": vector_weight,
        "keyword_weight": keyword_weight,
        "threshold": threshold,
        "top_k": top_k,
    }

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            return cursor.fetchall()


def main() -> int:
    """환경변수를 불러오고 법령 검색을 실행합니다."""

    args = parse_args()

    # CLI 입력값 검증
    validate_args(args)

    # 프로젝트 공통 환경변수를 먼저 읽습니다.
    load_dotenv(PROJECT_ROOT / ".env")

    # database/.env가 있으면 해당 값을 우선 적용합니다.
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )

    print(f"검색 질문: {args.query}")
    print(f"카테고리: {args.category}")

    # 적재 시 사용한 것과 동일한 text-embedding-3-small을
    # 이용하여 사용자 질문의 Embedding을 만듭니다.
    query_embedding = create_embeddings(
        [args.query]
    )[0]

    results = search_laws(
        database_url=database_url,
        query=args.query,
        query_embedding=query_embedding,
        category=args.category,
        top_k=args.top_k,
        vector_weight=args.vector_weight,
        keyword_weight=args.keyword_weight,
        threshold=args.threshold,
    )

    if not results:
        print(
            "검색 결과가 없습니다. "
            "threshold를 낮추거나 법령 Chunk와 "
            "Embedding 적재 상태를 확인하세요."
        )
        return 0

    for rank, row in enumerate(results, start=1):
        (
            title,
            external_id,
            effective_date,
            chunk_index,
            content,
            source,
            url,
            vector_score,
            keyword_score,
            combined_score,
        ) = row

        print("=" * 70)
        print(f"[{rank}위] {title}")

        # 점수를 각각 출력해야 검색 품질의 원인을 확인할 수 있습니다.
        print(
            f"결합점수: {float(combined_score):.4f} / "
            f"Vector: {float(vector_score):.4f} / "
            f"Keyword: {float(keyword_score):.4f}"
        )

        print(
            f"ID: {external_id} / "
            f"시행일: {effective_date} / "
            f"Chunk: {chunk_index}"
        )

        # 전체 조문이 길 수 있으므로 앞부분만 출력합니다.
        print(content[:700])

        print(f"출처: {source}")
        print(f"원문: {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())