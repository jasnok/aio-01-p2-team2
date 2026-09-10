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


# ---------------------------------------------------------
# 프로젝트 패키지 경로 등록
# ---------------------------------------------------------

# 이 파일을 database 디렉터리에서 직접 실행해도
# 최상위 database 패키지를 찾을 수 있도록 프로젝트 루트를
# Python 모듈 검색 경로에 먼저 추가합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# 프로젝트 내부 모듈 import
# ---------------------------------------------------------

# database 패키지를 사용하는 import는 반드시
# PROJECT_ROOT를 sys.path에 추가한 다음에 배치해야 합니다.
from database.ingestion.text_quality import (
    validate_embedding_text,
)
from database.ingestion.chunkers.precedent import (
    build_precedent_chunks,
)
from database.ingestion.embedders.openai_embedder import (
    create_embeddings,
)
from database.ingestion.normalizers.precedent import (
    normalize_precedent_xml,
)
from database.ingestion.normalizers.precedent_pdf import (
    normalize_precedent_pdf,
)

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

    parser.add_argument(
        "--only-new",
        action="store_true",
        help=(
            "DB에 동일한 source_name + external_id와 "
            "Embedding이 존재하는 판례는 건너뜁니다."
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

def filter_new_or_incomplete_documents(
    database_url: str,
    documents_and_chunks,
):
    """
    다음 문서만 적재 대상으로 반환합니다.

    1. DB에 없는 신규 문서
    2. DB에는 있지만 본문이 변경된 문서
    3. DB에는 있지만 Chunk나 Embedding이 누락된 문서

    동일한 본문과 정상 Embedding이 이미 있는 문서는 건너뜁니다.
    """

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.source_name,
                    d.external_id,
                    d.content_hash,

                    -- Chunk가 하나 이상 존재하고 모든 Chunk에
                    -- Embedding이 있으면 완료된 문서로 판단합니다.
                    (
                        COUNT(c.id) > 0
                        AND COUNT(c.embedding) = COUNT(c.id)
                    ) AS fully_embedded

                FROM legal_documents d
                LEFT JOIN legal_chunks c
                    ON c.document_id = d.id

                WHERE d.document_type = 'CASE'

                GROUP BY
                    d.id,
                    d.source_name,
                    d.external_id,
                    d.content_hash
                """
            )

            existing_documents = {
                (source_name, external_id): {
                    "content_hash": content_hash,
                    "fully_embedded": fully_embedded,
                }
                for (
                    source_name,
                    external_id,
                    content_hash,
                    fully_embedded,
                ) in cursor.fetchall()
            }

    targets = []
    skipped_count = 0
    new_count = 0
    changed_count = 0
    incomplete_count = 0

    for document, chunks in documents_and_chunks:
        key = (
            document.source_name,
            document.external_id,
        )

        existing = existing_documents.get(key)

        # DB에 없는 판례는 신규 적재합니다.
        if existing is None:
            print(
                "신규 판례: "
                f"{document.category} / "
                f"{document.case_number}"
            )

            targets.append((document, chunks))
            new_count += 1
            continue

        # PDF 내용이 변경되었다면 다시 적재하고 임베딩합니다.
        if (
            existing["content_hash"]
            != document.content_hash
        ):
            print(
                "본문 변경 판례: "
                f"{document.category} / "
                f"{document.case_number}"
            )

            targets.append((document, chunks))
            changed_count += 1
            continue

        # Chunk 또는 Embedding이 누락된 문서는 복구 대상으로 포함합니다.
        if not existing["fully_embedded"]:
            print(
                "Embedding 미완료 판례: "
                f"{document.category} / "
                f"{document.case_number}"
            )

            targets.append((document, chunks))
            incomplete_count += 1
            continue

        # 동일 본문과 정상 Embedding이 모두 있으면 건너뜁니다.
        print(
            "기존 완료 판례 건너뜀: "
            f"{document.category} / "
            f"{document.case_number}"
        )

        skipped_count += 1

    print()
    print(f"신규 판례: {new_count}건")
    print(f"본문 변경 판례: {changed_count}건")
    print(f"Embedding 미완료 판례: {incomplete_count}건")
    print(f"기존 완료 판례 제외: {skipped_count}건")
    print(f"최종 처리 대상: {len(targets)}건")

    return targets

def embed_chunks(
    documents_and_chunks,
):
    """
    Chunk 품질을 먼저 확인한 후 OpenAI 요청을 실행합니다.

    품질검사에서 실패하면 임베딩 API를 호출하지 않습니다.
    """

    all_chunks_with_documents = [
        (document, chunk)
        for document, chunks in documents_and_chunks
        for chunk in chunks
    ]

    # ---------------------------------------------
    # 1. 임베딩 이전 전체 Chunk 품질검사
    # ---------------------------------------------
    for document, chunk in all_chunks_with_documents:
        validate_embedding_text(
            content=chunk.content,
            source=(
                f"{document.category} / "
                f"{document.case_number} / "
                f"chunk={chunk.chunk_index}"
            ),
        )

    print(
        "Embedding 사전 품질검사 완료: "
        f"{len(all_chunks_with_documents)}개 Chunk"
    )

    # ---------------------------------------------
    # 2. 검사 통과 Chunk만 Embedding
    # ---------------------------------------------
    all_chunks = [
        chunk
        for _, chunk in all_chunks_with_documents
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
    """
    판례 원본을 읽고 필요하면 신규·변경·미완료 문서만
    PostgreSQL과 pgvector에 적재합니다.
    """

    # -----------------------------------------------------
    # 1. 명령행 옵션 확인
    # -----------------------------------------------------

    args = parse_args()

    # Embedding은 DB에 저장할 때만 생성합니다.
    # --with-embeddings만 단독으로 실행하는 실수를 방지합니다.
    if (
        args.with_embeddings
        and not args.load_db
    ):
        raise ValueError(
            "--with-embeddings는 "
            "--load-db와 함께 사용하세요."
        )


    # -----------------------------------------------------
    # 2. 환경변수 로드
    # -----------------------------------------------------

    # 프로젝트 최상위 .env를 먼저 읽습니다.
    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    # database/.env가 있으면 해당 값으로 덮어씁니다.
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    database_url = os.getenv(
        "DATABASE_URL"
    )

    # --load-db는 DB에 저장해야 하므로 DATABASE_URL이 필요합니다.
    #
    # --only-new는 DB를 변경하지 않는 검증 실행에서도
    # 기존 문서 목록을 조회해야 하므로 DATABASE_URL이 필요합니다.
    if (
        args.load_db
        or args.only_new
    ) and not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )


    # -----------------------------------------------------
    # 3. XML 또는 PDF 원본 정규화 및 Chunk 생성
    # -----------------------------------------------------

    documents_and_chunks = load_precedents(
        selected_category=args.category,
        source=args.source,
    )

    print()
    print(
        "원본에서 확인된 판례 수: "
        f"{len(documents_and_chunks)}"
    )


    # -----------------------------------------------------
    # 4. 기존 완료 문서 제외
    # -----------------------------------------------------

    if args.only_new:
        # 이 필터는 반드시 Embedding 생성 전에 실행해야 합니다.
        #
        # 그래야 이미 DB와 pgvector에 정상 적재된 문서에 대해
        # OpenAI Embedding을 다시 생성하지 않습니다.
        documents_and_chunks = (
            filter_new_or_incomplete_documents(
                database_url=database_url,
                documents_and_chunks=documents_and_chunks,
            )
        )


    # -----------------------------------------------------
    # 5. 이번 실행에서 실제로 처리할 대상 출력
    # -----------------------------------------------------

    print()
    print("처리 대상 판례")
    print("=" * 70)

    for document, chunks in documents_and_chunks:
        print(
            f"판례: {document.case_number} / "
            f"{document.title} / "
            f"분야: {document.category} / "
            f"Chunk: {len(chunks)}"
        )


    # -----------------------------------------------------
    # 6. 처리할 판례가 없으면 정상 종료
    # -----------------------------------------------------

    if not documents_and_chunks:
        print()
        print(
            "신규·변경·Embedding 미완료 "
            "판례가 없습니다."
        )

        # 처리 대상이 없으므로 OpenAI API를 호출하지 않습니다.
        return 0


    # -----------------------------------------------------
    # 7. --load-db가 없으면 검증만 하고 종료
    # -----------------------------------------------------

    if not args.load_db:
        print()
        print(
            "대상 확인만 완료했습니다. "
            "DB는 변경하지 않았습니다."
        )

        return 0


    # -----------------------------------------------------
    # 8. 처리 대상으로 확정된 Chunk만 Embedding
    # -----------------------------------------------------

    embeddings = (
        embed_chunks(
            documents_and_chunks
        )
        if args.with_embeddings
        else None
    )


    # -----------------------------------------------------
    # 9. PostgreSQL 및 pgvector 적재
    # -----------------------------------------------------

    save_to_database(
        database_url=database_url,
        documents_and_chunks=documents_and_chunks,
        embeddings=embeddings,
    )


    # -----------------------------------------------------
    # 10. 최종 실행 결과 출력
    # -----------------------------------------------------

    print()
    print("=" * 70)

    print(
        "DB 적재 판례 수: "
        f"{len(documents_and_chunks)}"
    )

    print(
        "Embedding 생성 수: "
        f"{len(embeddings) if embeddings else 0}"
    )

    print("판례 적재가 완료되었습니다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())