"""
중앙노동위원회 주요판정사례 CSV 정규화 모듈

원본에는 판정문 전체가 없고 사례 제목만 있으므로,
MVP에서는 제목 기반 ADMIN_DECISION 문서로 저장합니다.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterator

from database.ingestion.models import (
    NormalizedLegalDocument,
)


EXPECTED_HEADERS = (
    "구분",
    "순번",
    "자료구분",
    "제목",
    "위원회명",
    "작성일자",
    "조회수",
)

SOURCE_NAME = "중앙노동위원회 주요판정사례"

# 실제 data.go.kr 상세주소를 알고 있다면 그 주소로 교체합니다.
SOURCE_URL = "https://www.data.go.kr/"


def parse_date(value: str):
    value = value.strip()

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        )
    except ValueError:
        return None


def normalize_labor_decision_csv(
    csv_path: Path,
    limit: int | None = None,
) -> Iterator[NormalizedLegalDocument]:

    # 확인한 실제 파일 인코딩은 CP949입니다.
    with csv_path.open(
        "r",
        encoding="cp949",
        newline="",
    ) as stream:
        reader = csv.DictReader(stream)

        headers = tuple(reader.fieldnames or ())

        if headers != EXPECTED_HEADERS:
            raise ValueError(
                f"예상하지 못한 CSV 헤더입니다: {headers}"
            )

        emitted_count = 0

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            sequence = row["순번"].strip()
            decision_type = row["자료구분"].strip()
            title = row["제목"].strip()
            committee_name = row["위원회명"].strip()
            written_at = row["작성일자"].strip()

            if not sequence or not title:
                print(
                    f"건너뜀: {row_number}행 "
                    "순번 또는 제목 없음"
                )
                continue

            content = "\n".join(
                [
                    f"판정 유형: {decision_type}",
                    f"위원회: {committee_name}",
                    f"사례 제목: {title}",
                ]
            )

            content_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()

            yield NormalizedLegalDocument(
                external_id=(
                    f"nlrc-decision-{sequence}"
                ),
                document_type="ADMIN_DECISION",
                category="labor",
                title=title,
                summary=title,
                content=content,
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                source_type="file",
                raw_file=csv_path.as_posix(),
                content_hash=content_hash,
                source_updated_at=parse_date(written_at),
                metadata={
                    "categories": ["labor"],
                    "decision_type": decision_type,
                    "committee_name": committee_name,
                    "written_at": written_at,
                    "view_count": row["조회수"].strip(),

                    # 판정문 전문이 없다는 사실을 명시합니다.
                    "full_text_available": False,
                    "rag_enabled": True,
                },
            )

            emitted_count += 1

            if (
                limit is not None
                and emitted_count >= limit
            ):
                break