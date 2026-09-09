"""
수집된 판례 XML을 PostgreSQL과 pgvector에 적재합니다.
판례 본문·Chunk·Embedding을 실제 DB에 적재하는 파일입니다.
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


from database.ingestion.chunkers.precedent import (build_precedent_chunks,)
from database.ingestion.embedders.openai_embedder import ( create_embeddings,)
from database.ingestion.normalizers.precedent import (normalize_precedent_xml,)
from database.ingestion.normalizers.precedent_pdf import (normalize_precedent_pdf)

# 국가법령정보센터 API에서 수집한 판례 XML 경로
RAW_API_CASE_DIR = (
    PROJECT_ROOT
    / "database"
    / "raw"
    / "api"
    / "cases"
)

# 직접 확보한 판례 PDF 경로
RAW_FILE_CASE_DIR = (
    PROJECT_ROOT
    / "database"
    / "raw"
    / "files"
)

CATEGORIES = ("housing", "labor", "consumer")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="판례 XML DB·Embedding 적재"
    )

    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default=None,
        help="한 카테고리만 처리합니다. 생략하면 전체 처리합니다.",
    )

    parser.add_argument(
        "--load-db",
        action="store_true",
        help="판례와 Chunk를 PostgreSQL에 적재합니다.",
    )

    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="OpenAI Embedding을 만들어 pgvector에 저장합니다.",
    )

    parser.add_argument(
        "--source",
        choices=("api", "files", "all"),
        default="all",
        help=(
            "api는 국가법령정보센터 XML, "
            "files는 PDF, all은 둘 다 처리합니다."
        )
    )

    return parser.parse_args()


def load_precedents(
    selected_category: str | None,
    source: str,
):
    """
    API XML과 파일 PDF를 공통 판례 모델로 변환합니다.
    """

    categories = (
        [selected_category]
        if selected_category
        else list(CATEGORIES)
    )

    results = []

    for category in categories:

        # -------------------------------------------------
        # 1. 국가법령정보센터 API 판례 XML
        # -------------------------------------------------
        if source in ("api", "all"):
            api_category_dir = (
                RAW_API_CASE_DIR / category
            )

            if api_category_dir.exists():
                for xml_path in sorted(
                    api_category_dir.glob("prec_*.xml")
                ):
                    precedent = normalize_precedent_xml(
                        xml_path=xml_path,
                        category=category,
                    )

                    chunks = build_precedent_chunks(
                        precedent
                    )

                    results.append(
                        (precedent.document, chunks)
                    )

        # -------------------------------------------------
        # 2. raw/files 카테고리별 판례 PDF
        # -------------------------------------------------
        if source in ("files", "all"):
            file_category_dir = (
                RAW_FILE_CASE_DIR / category
            )

            if file_category_dir.exists():
                for pdf_path in sorted(
                    file_category_dir.glob("*.pdf")
                ):
                    precedent = normalize_precedent_pdf(
                        pdf_path=pdf_path,
                        category=category,
                    )

                    # API XML 판례와 PDF 판례 모두 동일한
                    # 판례 Chunk 생성기를 사용합니다.
                    chunks = build_precedent_chunks(
                        precedent
                    )

                    results.append(
                        (precedent.document, chunks)
                    )

    if not results:
        raise ValueError(
            "처리할 판례 XML 또는 PDF가 없습니다."
        )

    return results

def embed_chunks(
    documents_and_chunks,
):
    """OpenAI 요청을 50개 Chunk 단위로 실행합니다."""

    all_chunks = [
        chunk
        for _, chunks in documents_and_chunks
        for chunk in chunks
    ]

    embeddings: list[list[float]] = []
    batch_size = 50

    for start in range(
        0,
        len(all_chunks),
        batch_size,
    ):
        batch = all_chunks[
            start:start + batch_size
        ]

        batch_embeddings = create_embeddings(
            [chunk.content for chunk in batch]
        )

        embeddings.extend(batch_embeddings)

        print(
            "Embedding 진행: "
            f"{min(start + batch_size, len(all_chunks))}"
            f"/{len(all_chunks)}"
        )

    return embeddings


def save_to_database(
    database_url,
    documents_and_chunks,
    embeddings,
):
    """판례 문서와 Chunk를 Upsert합니다."""

    embedding_index = 0

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            for document, chunks in documents_and_chunks:
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        external_id,
                        document_type,
                        category,
                        title,
                        summary,
                        content,
                        law_name,
                        article_number,
                        case_number,
                        case_name,
                        court,
                        decided_at,
                        judgment_result,
                        source_name,
                        source_url,
                        source_type,
                        raw_file,
                        effective_date,
                        source_updated_at,
                        content_hash,
                        metadata,
                        updated_at
                    )
                    VALUES (
                        %(external_id)s,
                        %(document_type)s,
                        %(category)s,
                        %(title)s,
                        %(summary)s,
                        %(content)s,
                        %(law_name)s,
                        %(article_number)s,
                        %(case_number)s,
                        %(case_name)s,
                        %(court)s,
                        %(decided_at)s,
                        %(judgment_result)s,
                        %(source_name)s,
                        %(source_url)s,
                        %(source_type)s,
                        %(raw_file)s,
                        %(effective_date)s,
                        %(source_updated_at)s,
                        %(content_hash)s,
                        %(metadata)s,
                        NOW()
                    )
                    ON CONFLICT (
                        source_name,
                        external_id
                    )
                    DO UPDATE SET
                        document_type = EXCLUDED.document_type,
                        category = EXCLUDED.category,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content = EXCLUDED.content,
                        case_number = EXCLUDED.case_number,
                        case_name = EXCLUDED.case_name,
                        court = EXCLUDED.court,
                        decided_at = EXCLUDED.decided_at,
                        judgment_result = EXCLUDED.judgment_result,
                        source_url = EXCLUDED.source_url,
                        source_type = EXCLUDED.source_type,
                        raw_file = EXCLUDED.raw_file,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    {
                        **document.model_dump(
                            exclude={"metadata"}
                        ),
                        "metadata": Jsonb(
                            document.metadata
                        ),
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
                            document_id,
                            chunk_index,
                            section_type,
                            content,
                            token_count,
                            embedding,
                            embedding_model,
                            embedding_version,
                            content_hash,
                            updated_at
                        )
                        VALUES (
                            %(document_id)s,
                            %(chunk_index)s,
                            %(section_type)s,
                            %(content)s,
                            %(token_count)s,
                            %(embedding)s,
                            %(embedding_model)s,
                            %(embedding_version)s,
                            %(content_hash)s,
                            NOW()
                        )
                        ON CONFLICT (
                            document_id,
                            chunk_index
                        )
                        DO UPDATE SET
                            section_type = EXCLUDED.section_type,
                            content = EXCLUDED.content,
                            token_count = EXCLUDED.token_count,
                            embedding = CASE
                                WHEN legal_chunks.content_hash
                                    <> EXCLUDED.content_hash
                                THEN EXCLUDED.embedding
                                ELSE COALESCE(
                                    EXCLUDED.embedding,
                                    legal_chunks.embedding
                                )
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

                # 이전 실행에서 더 많이 생성된 Chunk가 남지 않도록 제거합니다.
                cursor.execute(
                    """
                    DELETE FROM legal_chunks
                    WHERE document_id = %s
                      AND chunk_index >= %s
                    """,
                    (
                        document_id,
                        len(chunks),
                    ),
                )

                print(
                    f"DB 적재: {document.case_number} "
                    f"{document.title} "
                    f"({len(chunks)}개 Chunk)"
                )

        connection.commit()


def main() -> int:
    args = parse_args()

    if (
        args.with_embeddings
        and not args.load_db
    ):
        raise ValueError(
            "--with-embeddings는 "
            "--load-db와 함께 사용하세요."
        )

    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    documents_and_chunks = load_precedents(
        selected_category=args.category,
        source=args.source,
    )

    for document, chunks in documents_and_chunks:
        print(
            f"판례: {document.case_number} / "
            f"{document.title} / "
            f"분야: {document.category} / "
            f"Chunk: {len(chunks)}"
        )

    if not args.load_db:
        print("DB는 변경하지 않았습니다.")
        return 0

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )

    embeddings = (
        embed_chunks(documents_and_chunks)
        if args.with_embeddings
        else None
    )

    save_to_database(
        database_url=database_url,
        documents_and_chunks=documents_and_chunks,
        embeddings=embeddings,
    )

    print(
        f"DB 적재 판례 수: "
        f"{len(documents_and_chunks)}"
    )

    print(
        f"Embedding 생성 수: "
        f"{len(embeddings) if embeddings else 0}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())