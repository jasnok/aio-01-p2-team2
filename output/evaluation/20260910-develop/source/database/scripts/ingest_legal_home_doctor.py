"""
법률홈닥터 우수사례집 PDF를 사례별로 분리하여
PostgreSQL과 pgvector에 적재합니다.

실행 위치:
    database/

대상 확인:
    python scripts/ingest_legal_home_doctor.py --only-new

적재:
    python scripts/ingest_legal_home_doctor.py \
        --only-new \
        --load-db \
        --with-embeddings

주의:
- 법원 판례가 아니므로 document_type은 GUIDELINE입니다.
- 실제 PDF 파일을 여러 파일로 분할하지 않습니다.
- PDF 한 장에 포함된 책의 좌우 페이지를 각각 추출합니다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb


# ---------------------------------------------------------
# 프로젝트 경로 설정
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.embedders.openai_embedder import (
    create_embeddings,
)
from database.ingestion.models import (
    LegalChunk,
    NormalizedLegalDocument,
)
from database.ingestion.text_quality import (
    validate_embedding_text,
)


MANIFEST_PATH = (
    PROJECT_ROOT
    / "database"
    / "sources"
    / "legal_home_doctor_2014.json"
)

MAX_CHUNK_CHARACTERS = 2400
OVERLAP_CHARACTERS = 250


# ---------------------------------------------------------
# 실행 옵션
# ---------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "법률홈닥터 우수사례집 사례별 적재"
        )
    )

    parser.add_argument(
        "--category",
        choices=("housing", "labor", "consumer"),
        default=None,
        help=(
            "특정 카테고리만 처리합니다. "
            "생략하면 활성화된 전체 사례를 처리합니다."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 사례 수를 제한합니다.",
    )

    parser.add_argument(
        "--only-new",
        action="store_true",
        help=(
            "신규·본문 변경·Embedding 미완료 "
            "사례만 처리합니다."
        ),
    )

    parser.add_argument(
        "--load-db",
        action="store_true",
        help="PostgreSQL에 실제로 저장합니다.",
    )

    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help=(
            "text-embedding-3-small Embedding을 "
            "생성하여 저장합니다."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------
# Manifest
# ---------------------------------------------------------

def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest가 없습니다: {MANIFEST_PATH}"
        )

    return json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


def resolve_raw_file(
    manifest: dict,
) -> Path:
    raw_file = Path(manifest["raw_file"])

    if not raw_file.is_absolute():
        raw_file = PROJECT_ROOT / raw_file

    if not raw_file.exists():
        raise FileNotFoundError(
            f"법률홈닥터 PDF가 없습니다: {raw_file}"
        )

    return raw_file


# ---------------------------------------------------------
# PDF 좌우 페이지 추출
# ---------------------------------------------------------

def extract_logical_pages(
    pdf_path: Path,
) -> dict[int, str]:
    """
    PDF 한 장에 들어 있는 책의 왼쪽·오른쪽 페이지를
    각각 추출하여 인쇄 페이지 번호와 연결합니다.

    사례 본문이 시작되는 구간에서는 다음 관계를 사용합니다.

        PDF 8페이지 왼쪽  → 책 12페이지
        PDF 8페이지 오른쪽 → 책 13페이지

    따라서 PDF 페이지가 n이면:
        왼쪽 책 페이지  = 2*n - 4
        오른쪽 책 페이지 = 2*n - 3
    """

    logical_pages: dict[int, str] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for pdf_page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):
            # 사례 본문은 PDF 8페이지 이후부터 시작합니다.
            if pdf_page_number < 8:
                continue

            middle_x = page.width / 2

            left_page = page.crop(
                (
                    0,
                    0,
                    middle_x,
                    page.height,
                )
            )

            right_page = page.crop(
                (
                    middle_x,
                    0,
                    page.width,
                    page.height,
                )
            )

            left_text = left_page.extract_text(
                x_tolerance=2,
                y_tolerance=3,
            ) or ""

            right_text = right_page.extract_text(
                x_tolerance=2,
                y_tolerance=3,
            ) or ""

            left_book_page = (
                2 * pdf_page_number - 4
            )

            right_book_page = (
                2 * pdf_page_number - 3
            )

            if left_text.strip():
                logical_pages[left_book_page] = (
                    clean_casebook_text(left_text)
                )

            if right_text.strip():
                logical_pages[right_book_page] = (
                    clean_casebook_text(right_text)
                )

    if not logical_pages:
        raise ValueError(
            "PDF에서 사례 본문 페이지를 "
            "추출하지 못했습니다."
        )

    return logical_pages


# ---------------------------------------------------------
# 텍스트 정리
# ---------------------------------------------------------

def clean_casebook_text(
    value: str,
) -> str:
    """
    사례집에서 반복되는 머리말·꼬리말과
    텍스트 추출용 가운데점을 정리합니다.
    """

    if not value:
        return ""

    value = value.replace("\x00", " ")

    # PDF에서 단어 사이에 사용된 가운데점을 공백으로 변경합니다.
    value = value.replace("·", " ")

    # 반복 머리말을 제거합니다.
    value = re.sub(
        r"법률홈닥터\s*우수사례집"
        r"(?:\s*Part\s*\d+_?\s*"
        r"법률홈닥터\s*우수사례\s*모음)?",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # 반복 꼬리말과 URL을 제거합니다.
    value = re.sub(
        r"서민에게\s*힘이\s*되는\s*법률홈닥터",
        " ",
        value,
    )

    value = re.sub(
        r"www\.moj\.go\.kr",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # 세로로 추출된 반복 장식 문구를 제거합니다.
    value = re.sub(
        r"법\s*\n?\s*률\s*\n?\s*홈\s*\n?\s*닥\s*"
        r"\n?\s*터\s*\n?\s*우\s*\n?\s*수\s*\n?\s*"
        r"사\s*\n?\s*례\s*\n?\s*모\s*\n?\s*음",
        " ",
        value,
    )

    # 한 줄에 페이지 번호만 있는 경우 제거합니다.
    value = re.sub(
        r"(?m)^\s*\d{1,3}\s*$",
        " ",
        value,
    )

    lines = []

    for line in value.splitlines():
        line = re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

        if line:
            lines.append(line)

    # 줄바꿈을 유지해 제목과 본문 경계를 확인할 수 있게 합니다.
    value = "\n".join(lines)

    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    return value.strip()


# ---------------------------------------------------------
# 사례별 문서 정규화
# ---------------------------------------------------------

def normalize_documents(
    manifest: dict,
    logical_pages: dict[int, str],
    selected_category: str | None,
    limit: int | None,
) -> list[NormalizedLegalDocument]:
    documents: list[NormalizedLegalDocument] = []

    for case_info in manifest["cases"]:
        if not case_info.get("enabled", False):
            continue

        category = case_info["category"]

        if (
            selected_category is not None
            and category != selected_category
        ):
            continue

        start_page = int(
            case_info["start_page"]
        )

        end_page = int(
            case_info["end_page"]
        )

        page_texts = []

        for page_number in range(
            start_page,
            end_page + 1,
        ):
            page_text = logical_pages.get(
                page_number,
                "",
            )

            if page_text:
                page_texts.append(page_text)

        case_content = "\n\n".join(
            page_texts
        ).strip()

        if not case_content:
            raise ValueError(
                "사례 본문을 추출하지 못했습니다: "
                f"{case_info['case_number']}번 / "
                f"{case_info['title']}"
            )

        title = case_info["title"]

        full_content = "\n".join(
            [
                "자료 유형: 법률지원 사례",
                f"발행기관: {manifest['source_name']}",
                (
                    "사례집: "
                    f"{manifest['publication_title']}"
                ),
                (
                    "사례 번호: "
                    f"{case_info['case_number']}"
                ),
                f"사례 제목: {title}",
                "",
                case_content,
            ]
        ).strip()

        content_hash = hashlib.sha256(
            full_content.encode("utf-8")
        ).hexdigest()

        external_id = (
            f"{manifest['source_id']}-case-"
            f"{int(case_info['case_number']):02d}"
        )

        document = NormalizedLegalDocument(
            external_id=external_id,
            document_type="GUIDELINE",
            category=category,
            title=title,
            summary=title,
            content=full_content,
            source_name=manifest["source_name"],
            source_url=manifest["source_url"],
            source_type="file",
            raw_file=manifest["raw_file"],
            content_hash=content_hash,
            metadata={
                "categories": [category],
                "publication_title": (
                    manifest["publication_title"]
                ),
                "publication_year": (
                    manifest["publication_year"]
                ),
                "case_number_in_book": (
                    case_info["case_number"]
                ),
                "printed_page_start": start_page,
                "printed_page_end": end_page,
                "content_kind": (
                    manifest["content_kind"]
                ),
                "full_text_available": True,
                "rag_enabled": True,
                "current_law_verification_required": True,
                "source_url_scope": (
                    "publisher_home"
                ),
                "text_extractor": "pdfplumber",
                "text_extractor_options": {
                    "split_spread_pages": True,
                    "x_tolerance": 2,
                    "y_tolerance": 3,
                },
            },
        )

        documents.append(document)

        if (
            limit is not None
            and len(documents) >= limit
        ):
            break

    if not documents:
        raise ValueError(
            "처리할 활성 사례가 없습니다."
        )

    return documents


# ---------------------------------------------------------
# 청크 생성
# ---------------------------------------------------------

def split_long_text(
    text: str,
    max_characters: int = MAX_CHUNK_CHARACTERS,
    overlap: int = OVERLAP_CHARACTERS,
) -> list[str]:
    text = text.strip()

    if not text:
        return []

    if len(text) <= max_characters:
        return [text]

    sentences = re.split(
        r"(?<=[.!?다요])\s+|\n+",
        text,
    )

    results: list[str] = []
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

        results.append(current)

        overlap_text = current[-overlap:]
        current = (
            f"{overlap_text} {sentence}"
        ).strip()

    if current:
        results.append(current)

    return results


def build_chunks(
    document: NormalizedLegalDocument,
) -> list[LegalChunk]:
    model = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    version = os.getenv(
        "EMBEDDING_VERSION",
        "v1",
    )

    split_contents = split_long_text(
        document.content
    )

    chunks: list[LegalChunk] = []

    for split_content in split_contents:
        chunk_content = "\n".join(
            [
                "자료 유형: 법률지원 사례",
                f"분야: {document.category}",
                f"사례 제목: {document.title}",
                f"내용: {split_content}",
            ]
        )

        validate_embedding_text(
            content=chunk_content,
            source=(
                f"{document.external_id} / "
                f"chunk={len(chunks)}"
            ),
        )

        chunks.append(
            LegalChunk(
                chunk_index=len(chunks),
                section_type="legal_aid_case",
                content=chunk_content,
                token_count=None,
                content_hash=hashlib.sha256(
                    chunk_content.encode("utf-8")
                ).hexdigest(),
                embedding_model=model,
                embedding_version=version,
            )
        )

    if not chunks:
        raise ValueError(
            f"사례 Chunk가 없습니다: {document.title}"
        )

    return chunks


# ---------------------------------------------------------
# 신규·변경·미완료 선별
# ---------------------------------------------------------

def filter_new_or_incomplete(
    database_url: str,
    documents_and_chunks,
):
    with psycopg.connect(
        database_url
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.source_name,
                    d.external_id,
                    d.content_hash,
                    (
                        COUNT(c.id) > 0
                        AND COUNT(c.embedding)
                            = COUNT(c.id)
                    ) AS fully_embedded
                FROM legal_documents d
                LEFT JOIN legal_chunks c
                    ON c.document_id = d.id
                WHERE d.document_type = 'GUIDELINE'
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

    new_count = 0
    changed_count = 0
    incomplete_count = 0
    skipped_count = 0

    for document, chunks in documents_and_chunks:
        key = (
            document.source_name,
            document.external_id,
        )

        existing = existing_documents.get(key)

        if existing is None:
            print(
                "신규 사례: "
                f"{document.external_id} / "
                f"{document.title}"
            )

            targets.append(
                (document, chunks)
            )

            new_count += 1
            continue

        if (
            existing["content_hash"]
            != document.content_hash
        ):
            print(
                "본문 변경 사례: "
                f"{document.external_id} / "
                f"{document.title}"
            )

            targets.append(
                (document, chunks)
            )

            changed_count += 1
            continue

        if not existing["fully_embedded"]:
            print(
                "Embedding 미완료 사례: "
                f"{document.external_id} / "
                f"{document.title}"
            )

            targets.append(
                (document, chunks)
            )

            incomplete_count += 1
            continue

        print(
            "기존 완료 사례 건너뜀: "
            f"{document.external_id} / "
            f"{document.title}"
        )

        skipped_count += 1

    print()
    print(f"신규 사례: {new_count}건")
    print(f"본문 변경 사례: {changed_count}건")
    print(
        "Embedding 미완료 사례: "
        f"{incomplete_count}건"
    )
    print(
        "기존 완료 사례 제외: "
        f"{skipped_count}건"
    )
    print(
        "최종 처리 대상: "
        f"{len(targets)}건"
    )

    return targets


# ---------------------------------------------------------
# Embedding 생성
# ---------------------------------------------------------

def embed_chunks(
    documents_and_chunks,
) -> list[list[float]]:
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
            [
                chunk.content
                for chunk in batch
            ]
        )

        embeddings.extend(
            batch_embeddings
        )

        print(
            "Embedding 진행: "
            f"{min(start + batch_size, len(all_chunks))}"
            f"/{len(all_chunks)}"
        )

    return embeddings


# ---------------------------------------------------------
# DB Upsert
# ---------------------------------------------------------

def save_to_database(
    database_url: str,
    documents_and_chunks,
    embeddings: list[list[float]] | None,
) -> None:
    embedding_index = 0

    with psycopg.connect(
        database_url
    ) as connection:
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
                        source_name,
                        source_url,
                        source_type,
                        raw_file,
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
                        %(source_name)s,
                        %(source_url)s,
                        %(source_type)s,
                        %(raw_file)s,
                        %(content_hash)s,
                        %(metadata)s,
                        NOW()
                    )
                    ON CONFLICT (
                        source_name,
                        external_id
                    )
                    DO UPDATE SET
                        document_type =
                            EXCLUDED.document_type,
                        category =
                            EXCLUDED.category,
                        title =
                            EXCLUDED.title,
                        summary =
                            EXCLUDED.summary,
                        content =
                            EXCLUDED.content,
                        source_url =
                            EXCLUDED.source_url,
                        source_type =
                            EXCLUDED.source_type,
                        raw_file =
                            EXCLUDED.raw_file,
                        content_hash =
                            EXCLUDED.content_hash,
                        metadata =
                            EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    {
                        "external_id": (
                            document.external_id
                        ),
                        "document_type": (
                            document.document_type
                        ),
                        "category": (
                            document.category
                        ),
                        "title": document.title,
                        "summary": document.summary,
                        "content": document.content,
                        "source_name": (
                            document.source_name
                        ),
                        "source_url": (
                            document.source_url
                        ),
                        "source_type": (
                            document.source_type
                        ),
                        "raw_file": document.raw_file,
                        "content_hash": (
                            document.content_hash
                        ),
                        "metadata": Jsonb(
                            document.metadata
                        ),
                    },
                )

                document_id = (
                    cursor.fetchone()[0]
                )

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
                            section_type =
                                EXCLUDED.section_type,
                            content =
                                EXCLUDED.content,
                            token_count =
                                EXCLUDED.token_count,
                            embedding = CASE
                                WHEN
                                    legal_chunks.content_hash
                                    <> EXCLUDED.content_hash
                                THEN EXCLUDED.embedding
                                ELSE COALESCE(
                                    EXCLUDED.embedding,
                                    legal_chunks.embedding
                                )
                            END,
                            embedding_model = CASE
                                WHEN
                                    EXCLUDED.embedding
                                    IS NOT NULL
                                THEN
                                    EXCLUDED.embedding_model
                                ELSE
                                    legal_chunks.embedding_model
                            END,
                            embedding_version = CASE
                                WHEN
                                    EXCLUDED.embedding
                                    IS NOT NULL
                                THEN
                                    EXCLUDED.embedding_version
                                ELSE
                                    legal_chunks.embedding_version
                            END,
                            content_hash =
                                EXCLUDED.content_hash,
                            updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            "chunk_index": (
                                chunk.chunk_index
                            ),
                            "section_type": (
                                chunk.section_type
                            ),
                            "content": chunk.content,
                            "token_count": (
                                chunk.token_count
                            ),
                            "embedding": embedding,
                            "embedding_model": (
                                chunk.embedding_model
                            ),
                            "embedding_version": (
                                chunk.embedding_version
                            ),
                            "content_hash": (
                                chunk.content_hash
                            ),
                        },
                    )

                # 이전 실행에서 더 많이 생성된 청크를 제거합니다.
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
                    "DB 적재: "
                    f"{document.external_id} / "
                    f"{document.title} / "
                    f"{len(chunks)}개 Chunk"
                )

        connection.commit()


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------

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

    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if (
        args.only_new
        or args.load_db
    ) and not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 없습니다."
        )

    manifest = load_manifest()
    pdf_path = resolve_raw_file(
        manifest
    )

    print(f"원본 PDF: {pdf_path}")

    logical_pages = extract_logical_pages(
        pdf_path
    )

    print(
        "추출된 책 페이지 수: "
        f"{len(logical_pages)}"
    )

    documents = normalize_documents(
        manifest=manifest,
        logical_pages=logical_pages,
        selected_category=args.category,
        limit=args.limit,
    )

    documents_and_chunks = [
        (
            document,
            build_chunks(document),
        )
        for document in documents
    ]

    print()
    print(
        "정규화 사례 수: "
        f"{len(documents_and_chunks)}"
    )

    if args.only_new:
        documents_and_chunks = (
            filter_new_or_incomplete(
                database_url=database_url,
                documents_and_chunks=(
                    documents_and_chunks
                ),
            )
        )

    print()
    print("처리 대상 법률지원 사례")
    print("=" * 70)

    for document, chunks in documents_and_chunks:
        print(
            f"{document.external_id} / "
            f"{document.category} / "
            f"{document.title} / "
            f"Chunk: {len(chunks)}"
        )

    if not documents_and_chunks:
        print(
            "신규·변경·Embedding 미완료 "
            "사례가 없습니다."
        )

        return 0

    if not args.load_db:
        print(
            "대상 확인만 완료했습니다. "
            "DB는 변경하지 않았습니다."
        )

        return 0

    embeddings = (
        embed_chunks(
            documents_and_chunks
        )
        if args.with_embeddings
        else None
    )

    save_to_database(
        database_url=database_url,
        documents_and_chunks=documents_and_chunks,
        embeddings=embeddings,
    )

    print()
    print(
        "DB 적재 사례 수: "
        f"{len(documents_and_chunks)}"
    )

    print(
        "Embedding 생성 수: "
        f"{len(embeddings) if embeddings else 0}"
    )

    print(
        "법률홈닥터 사례 적재가 완료되었습니다."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())