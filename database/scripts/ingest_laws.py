"""수집된 현행 법령 XML을 PostgreSQL/pgvector에 적재합니다.

실행 모드
---------
``python scripts/ingest_laws.py``
    정규화와 Chunk 결과만 출력합니다. DB와 OpenAI를 사용하지 않습니다.

``python scripts/ingest_laws.py --load-db``
    법령 문서와 조문 Chunk를 DB에 적재합니다. Embedding은 만들지 않습니다.

``python scripts/ingest_laws.py --load-db --with-embeddings``
    ``text-embedding-3-small`` Embedding까지 만들어 pgvector에 저장합니다.

이 파일은 각 단계의 실행 순서를 조정합니다. XML 파싱은 normalizer,
Chunk 구성은 chunker, OpenAI 호출은 embedder에 위임합니다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.ingestion.chunkers.statute import build_statute_chunks
from database.ingestion.embedders.openai_embedder import create_embeddings
from database.ingestion.normalizers.statute import normalize_statute_xml


RAW_LAW_DIR = PROJECT_ROOT / "database" / "raw" / "api" / "laws"

# category는 현재 legal_documents의 대표 카테고리 한 개입니다.
# categories는 metadata JSONB에 저장되어 공용 법령 검색에 사용됩니다.
# 민법 원문은 한 번만 저장하고 housing과 consumer 양쪽에서 조회합니다.
# name:
#   PowerShell의 --law 옵션에서 선택할 정확한 법령명입니다.
#
# path:
#   database/raw/api/laws 아래에 있는 원본 XML 파일명입니다.
#
# category:
#   legal_documents.category에 저장할 대표 분야입니다.
#
# categories:
#   실제 검색에 허용할 전체 분야입니다.
#   민법은 housing과 consumer 양쪽에서 사용합니다.
LAW_FILES = [
    {"name": "민법","path": "민법.xml", "category": "housing", "categories": ["housing", "consumer"]},
    {"name": "주택임대차보호법","path": "주택임대차보호법.xml", "category": "housing", "categories": ["housing"],},
    { "name": "주택임대차보호법 시행령", "path": "주택임대차보호법_시행령.xml", "category": "housing", "categories": ["housing"],},
    { "name": "근로기준법", "path": "근로기준법.xml", "category": "labor", "categories": ["labor"],},
    { "name": "근로자퇴직급여 보장법", "path": "근로자퇴직급여_보장법.xml", "category": "labor", "categories": ["labor"],},
    {"name": "전자상거래 등에서의 소비자보호에 관한 법률", "path": "전자상거래법.xml", "category": "consumer", "categories": ["consumer"],},
    { "name": "소비자기본법", "path": "소비자기본법.xml", "category": "consumer", "categories": ["consumer"],},
    { "name": "형법", "path": "형법.xml", "category": "consumer", "categories": ["consumer"],},
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="현행 법령 XML 적재"
    )

    parser.add_argument(
        "--load-db",
        action="store_true",
        help="PostgreSQL에 법령 문서와 조문 Chunk를 적재합니다.",
    )

    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="OpenAI Embedding을 생성하여 pgvector에 저장합니다.",
    )

    parser.add_argument(
        "--law",
        dest="law_names",
        action="append",
        default=None,
        help=(
            "처리할 법령명을 지정합니다. "
            "여러 법령을 처리하려면 --law를 반복해서 입력합니다. "
            "생략하면 LAW_FILES의 모든 법령을 처리합니다."
        ),
    )

    return parser.parse_args()


def load_statutes(
    selected_law_names: list[str] | None = None,
):
    """
    설정된 법령 XML을 정규화하고 조문 Chunk를 생성합니다.

    selected_law_names가 None이면 전체 법령을 처리합니다.
    --law가 입력되면 해당 법령만 처리합니다.
    """

    # 설정에 등록된 정확한 법령명 목록입니다.
    configured_names = {
        config["name"]
        for config in LAW_FILES
    }

    if selected_law_names:
        # 오타가 있는 법령명을 조용히 무시하지 않고 실행 전에 중단합니다.
        unknown_names = (
            set(selected_law_names)
            - configured_names
        )

        if unknown_names:
            available = ", ".join(
                sorted(configured_names)
            )
            unknown = ", ".join(
                sorted(unknown_names)
            )

            raise ValueError(
                f"등록되지 않은 법령입니다: {unknown}\n"
                f"선택 가능한 법령: {available}"
            )

        selected_names = set(selected_law_names)
    else:
        # --law가 없으면 전체 법령을 처리합니다.
        selected_names = configured_names

    results = []

    for config in LAW_FILES:
        # 사용자가 지정하지 않은 법령은 XML 파싱과
        # Embedding 대상에서 제외합니다.
        if config["name"] not in selected_names:
            continue

        xml_path = (
            RAW_LAW_DIR
            / config["path"]
        )

        if not xml_path.exists():
            raise FileNotFoundError(
                f"법령 원본 파일이 없습니다: {xml_path}"
            )

        statute = normalize_statute_xml(
            xml_path=xml_path,
            category=config["category"],
            categories=config["categories"],
        )

        chunks = build_statute_chunks(statute)

        results.append(
            (
                statute.document,
                chunks,
            )
        )

    if not results:
        raise ValueError(
            "처리할 법령이 선택되지 않았습니다."
        )

    return results


def embed_chunks(documents_and_chunks):
    """API 요청 크기를 제한하기 위해 50개 Chunk씩 Embedding합니다."""
    all_chunks = [
        chunk
        for _, chunks in documents_and_chunks
        for chunk in chunks
    ]
    embeddings: list[list[float]] = []
    batch_size = 50

    for start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[start:start + batch_size]
        embeddings.extend(create_embeddings([chunk.content for chunk in batch]))
        print(f"Embedding 진행: {min(start + batch_size, len(all_chunks))}/{len(all_chunks)}")

    return embeddings


def save_to_database(database_url, documents_and_chunks, embeddings):
    """법령은 Upsert하고 Chunk는 본문 변경 여부에 맞춰 안전하게 갱신합니다.

    같은 법령을 다시 실행해도 ``source_name + external_id`` 유일키로 한 건만
    유지됩니다. 임베딩 없이 재실행하면 본문이 같은 기존 벡터는 보존하고,
    본문이 바뀐 Chunk의 벡터는 NULL로 만들어 잘못된 벡터 사용을 막습니다.
    """
    embedding_index = 0

    with psycopg.connect(database_url) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            for document, chunks in documents_and_chunks:
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        external_id, document_type, category, title, summary,
                        content, law_name, article_number, source_name,
                        source_url, source_type, raw_file, effective_date,
                        source_updated_at, content_hash, metadata, updated_at
                    ) VALUES (
                        %(external_id)s, %(document_type)s, %(category)s,
                        %(title)s, %(summary)s, %(content)s, %(law_name)s,
                        %(article_number)s, %(source_name)s, %(source_url)s,
                        %(source_type)s, %(raw_file)s, %(effective_date)s,
                        %(source_updated_at)s, %(content_hash)s, %(metadata)s,
                        NOW()
                    )
                    ON CONFLICT (source_name, external_id) DO UPDATE SET
                        document_type = EXCLUDED.document_type,
                        category = EXCLUDED.category,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content = EXCLUDED.content,
                        law_name = EXCLUDED.law_name,
                        source_url = EXCLUDED.source_url,
                        source_type = EXCLUDED.source_type,
                        raw_file = EXCLUDED.raw_file,
                        effective_date = EXCLUDED.effective_date,
                        source_updated_at = EXCLUDED.source_updated_at,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    {
                        **document.model_dump(exclude={"metadata"}),
                        "metadata": Jsonb(document.metadata),
                    },
                )
                document_id = cursor.fetchone()[0]

                for chunk in chunks:
                    embedding = (
                        embeddings[embedding_index]
                        if embeddings is not None
                        else None
                    )
                    if embeddings is not None:
                        embedding_index += 1

                    cursor.execute(
                        """
                        INSERT INTO legal_chunks (
                            document_id, chunk_index, section_type, content,
                            token_count, embedding, embedding_model,
                            embedding_version, content_hash, updated_at
                        ) VALUES (
                            %(document_id)s, %(chunk_index)s, %(section_type)s,
                            %(content)s, %(token_count)s, %(embedding)s,
                            %(embedding_model)s, %(embedding_version)s,
                            %(content_hash)s, NOW()
                        )
                        ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                            section_type = EXCLUDED.section_type,
                            content = EXCLUDED.content,
                            token_count = EXCLUDED.token_count,
                            embedding = CASE
                                WHEN legal_chunks.content_hash <> EXCLUDED.content_hash
                                    THEN EXCLUDED.embedding
                                ELSE COALESCE(EXCLUDED.embedding, legal_chunks.embedding)
                            END,
                            embedding_model = CASE
                                WHEN EXCLUDED.embedding IS NOT NULL
                                    THEN EXCLUDED.embedding_model
                                ELSE legal_chunks.embedding_model
                            END,
                            embedding_version = CASE
                                WHEN EXCLUDED.embedding IS NOT NULL
                                    THEN EXCLUDED.embedding_version
                                ELSE legal_chunks.embedding_version
                            END,
                            content_hash = EXCLUDED.content_hash,
                            updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            **chunk.model_dump(),
                            "embedding": embedding,
                        },
                    )

                # 개정으로 조문 수가 줄었을 경우 남는 예전 Chunk를 제거합니다.
                cursor.execute(
                    "DELETE FROM legal_chunks WHERE document_id = %s AND chunk_index >= %s",
                    (document_id, len(chunks)),
                )

                print(f"DB 적재: {document.title} ({len(chunks)}개 Chunk)")

        # 중간 실패 시 psycopg가 rollback하므로 전체가 성공했을 때만 반영됩니다.
        connection.commit()


def main() -> int:
    args = parse_args()
    if args.with_embeddings and not args.load_db:
        raise ValueError("--with-embeddings는 --load-db와 함께 사용하세요.")

    # 공통 설정을 읽고 DB 담당자 설정이 있으면 우선 적용합니다.
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / "database" / ".env", override=True)

    # documents_and_chunks = load_statutes()
    # --law로 지정한 법령만 정규화·Chunk·Embedding 대상으로 전달합니다.
    # --law를 생략하면 args.law_names는 None이므로 전체를 처리합니다.
    documents_and_chunks = load_statutes(selected_law_names=args.law_names)
    for document, chunks in documents_and_chunks:
        print(
            f"법령명: {document.title} | ID: {document.external_id} | "
            f"분야: {document.metadata['categories']} | Chunk: {len(chunks)}"
        )

    if not args.load_db:
        print("DB는 변경하지 않았습니다.")
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 없습니다.")

    embeddings = embed_chunks(documents_and_chunks) if args.with_embeddings else None
    save_to_database(database_url, documents_and_chunks, embeddings)
    print(f"DB 적재 법령 수: {len(documents_and_chunks)}")
    print(f"Embedding 생성 수: {len(embeddings) if embeddings else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
