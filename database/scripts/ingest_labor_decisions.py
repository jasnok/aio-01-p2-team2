"""
중앙노동위원회 주요판정사례 CSV를 DB와 pgvector에 적재합니다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.chunkers.labor_decision import (
    build_labor_decision_chunk,
)
from database.ingestion.normalizers.labor_decision import (
    normalize_labor_decision_csv,
)

# 기존 판례 적재 파일의 공통 Embedding 및 DB Upsert 함수를 재사용합니다.
from database.scripts.ingest_cases import (
    embed_chunks,
    save_to_database,
)


RAW_FILE = (
    PROJECT_ROOT
    / "database"
    / "raw"
    / "files"
    / "labor"
    / "고용노동부 중앙노동위원회_주요판정사례_20260506.csv"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="노동위원회 판정사례 적재"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="테스트할 사례 수. 생략하면 전체 처리합니다.",
    )

    parser.add_argument(
        "--load-db",
        action="store_true",
        help="PostgreSQL에 적재합니다.",
    )

    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="OpenAI Embedding을 생성합니다.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    if args.with_embeddings and not args.load_db:
        raise ValueError(
            "--with-embeddings는 "
            "--load-db와 함께 사용하세요."
        )

    documents = list(
        normalize_labor_decision_csv(
            csv_path=RAW_FILE,
            limit=args.limit,
        )
    )

    documents_and_chunks = [
        (
            document,
            [build_labor_decision_chunk(document)],
        )
        for document in documents
    ]

    print(f"정규화 문서 수: {len(documents)}")
    print(
        "문서 유형: ADMIN_DECISION "
        "(노동위원회 판정사례)"
    )

    if not args.load_db:
        print("검증만 완료했습니다. DB에는 저장하지 않았습니다.")
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

    print(f"DB 적재 문서 수: {len(documents)}")
    print(
        "Embedding 생성 수: "
        f"{len(embeddings) if embeddings else 0}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())