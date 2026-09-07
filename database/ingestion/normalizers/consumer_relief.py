"""
소비자원 SpreadsheetML XML 읽기
→ 일련번호·품목·제목·질문·답변 추출
→ NormalizedLegalDocument 생성
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

from database.ingestion.models import NormalizedLegalDocument


# 소비자원 XML은 일반 XML이 아니라 Excel SpreadsheetML 형식입니다.
# 따라서 아래 Namespace를 사용하지 않으면 Row와 Cell을 찾을 수 없습니다.
SPREADSHEET_NAMESPACE = (
    "urn:schemas-microsoft-com:office:spreadsheet"
)

NAMESPACES = {
    "ss": SPREADSHEET_NAMESPACE,
}

# 원본 XML의 헤더 순서입니다.
EXPECTED_HEADERS = (
    "일련번호",
    "품목",
    "출처",
    "제목",
    "질문",
    "답변",
)

# 모든 소비자원 문서에 공통으로 들어갈 출처 정보입니다.
SOURCE_NAME = "한국소비자원 품목별 피해구제 사례"

SOURCE_URL = (
    "https://www.data.go.kr/data/"
    "15090382/fileData.do?recommendDataYn=Y"
)


def read_cell_values(row: ET.Element) -> list[str]:
    """
    SpreadsheetML의 한 행에서 Cell 값을 순서대로 읽습니다.

    일부 Excel XML에는 ss:Index가 있어 빈 Cell이 생략될 수 있으므로
    Index를 확인해 누락된 위치에 빈 문자열을 추가합니다.
    """

    values: list[str] = []

    for cell in row.findall("ss:Cell", NAMESPACES):
        index = cell.get(
            f"{{{SPREADSHEET_NAMESPACE}}}Index"
        )

        # ss:Index가 3인데 현재 값이 1개뿐이라면
        # 중간의 비어 있는 Cell을 추가합니다.
        if index:
            while len(values) < int(index) - 1:
                values.append("")

        data = cell.find("ss:Data", NAMESPACES)

        if data is None:
            values.append("")
        else:
            # 줄바꿈과 내부 텍스트를 유지하면서 문자열로 변환합니다.
            value = "".join(data.itertext()).strip()
            values.append(value)

    return values


def create_content(
    title: str,
    item: str,
    question: str,
    answer: str,
) -> str:
    """
    RAG 검색과 Embedding에 사용할 본문을 만듭니다.

    질문만 저장하지 않고 제목·품목·질문·답변을 함께 넣어야
    사용자 표현과 유사한 피해구제 사례를 찾기 쉽습니다.
    """

    return "\n\n".join(
        [
            f"제목: {title}",
            f"품목: {item}",
            f"질문: {question}",
            f"답변: {answer}",
        ]
    )


def normalize_consumer_relief_xml(
    xml_path: Path,
    limit: int | None = None,
) -> Iterator[NormalizedLegalDocument]:
    """
    소비자원 XML을 읽어 공통 법률 문서 형식으로 변환합니다.

    limit=5로 호출하면 최초 검증용 5건만 반환합니다.
    limit=None이면 전체 678건을 반환합니다.
    """

    if limit is not None and limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Workbook 안의 모든 Worksheet/Table/Row를 조회합니다.
    rows = root.findall(
        ".//ss:Worksheet/ss:Table/ss:Row",
        NAMESPACES,
    )

    if not rows:
        raise ValueError(
            f"XML에서 데이터 행을 찾지 못했습니다: {xml_path}"
        )

    # 첫 번째 행은 데이터가 아니라 헤더입니다.
    headers = tuple(read_cell_values(rows[0]))

    if headers != EXPECTED_HEADERS:
        raise ValueError(
            f"예상하지 못한 XML 헤더입니다: {headers}"
        )

    emitted_count = 0

    # 두 번째 행부터 실제 소비자 사례입니다.
    for row_number, row in enumerate(rows[1:], start=2):
        values = read_cell_values(row)

        # Cell이 부족한 경우 헤더 개수까지 빈 값으로 채웁니다.
        values.extend(
            [""] * (len(EXPECTED_HEADERS) - len(values))
        )

        record = dict(
            zip(
                EXPECTED_HEADERS,
                values,
                strict=False,
            )
        )

        serial_number = record["일련번호"].strip()
        item = record["품목"].strip()
        original_source = record["출처"].strip()
        title = record["제목"].strip()
        question = record["질문"].strip()
        answer = record["답변"].strip()

        # RAG 문서를 만드는 데 필요한 필수값을 검증합니다.
        if not serial_number:
            raise ValueError(
                f"{row_number}행에 일련번호가 없습니다."
            )

        if not title or not question or not answer:
            raise ValueError(
                f"{row_number}행에 제목·질문·답변이 없습니다."
            )

        content = create_content(
            title=title,
            item=item,
            question=question,
            answer=answer,
        )

        # 동일한 본문인지 확인하기 위한 SHA-256입니다.
        content_hash = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

        yield NormalizedLegalDocument(
            external_id=f"kca-relief-{serial_number}",
            document_type="CONSULTATION",
            category="consumer",
            title=title,
            summary=question,
            content=content,
            source_name=SOURCE_NAME,
            source_url=SOURCE_URL,
            source_type="file",
            raw_file=xml_path.as_posix(),
            content_hash=content_hash,

            # 소비자원 원본에만 있는 값을 JSONB에 보관합니다.
            metadata={
                "serial_number": serial_number,
                "item": item,
                "original_source": original_source,
                "question": question,
                "answer": answer,
            },
        )

        emitted_count += 1

        # 최초 테스트에서는 5건만 처리할 수 있습니다.
        if limit is not None and emitted_count >= limit:
            break