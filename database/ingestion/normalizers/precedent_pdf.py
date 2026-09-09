"""
빅케이스에서 내려받은 판례 PDF를 공통 판례 모델로 변환합니다.

주의:
- 법원명, 선고일, 사건번호, 사건명은 파일명에서 추출합니다.
- 판결문 본문은 PDF에서 추출합니다.
- source_name은 판결 법원이 아니라 PDF 제공 서비스인 빅케이스입니다.
- 법원명은 legal_documents.court에 별도로 저장합니다.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader

from database.ingestion.models import (
    NormalizedLegalDocument,
    NormalizedPrecedent,
    NormalizedPrecedentSection,
)


SOURCE_NAME = "빅케이스"
#
# 지원 예시 1:
# 서울중앙지방법원 2026. 7. 16. 선고
# 2025가합11696 판결 대금반환.pdf
#
# 지원 예시 2:
# 서울중앙지방법원 2026. 7. 14. 선고
# 2025고단5296,2025고단100024(병합),....pdf
#
# 두 번째 파일처럼 "판결 사건명"이 없어도 처리합니다.
FILENAME_PATTERN = re.compile(
    r"^(?P<court>.+?)\s+"
    r"(?P<year>\d{4})\.\s*"
    r"(?P<month>\d{1,2})\.\s*"
    r"(?P<day>\d{1,2})\.\s*"
    r"선고\s+"
    r"(?P<remainder>.+)$"
)

def clean_text(value: str) -> str:
    """
    PDF 추출 과정에서 생기는 연속 공백과 빈 줄을 정리합니다.

    일부 PDF는 글자 사이에 불필요한 공백이 들어갈 수 있으므로
    실제 적재 전 추출 결과를 몇 건 반드시 확인해야 합니다.
    """

    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    # PDF 페이지마다 반복되는 빅케이스 안내문을 제거합니다.
    value = re.sub(
        r"\d{4}-\d{2}-\d{2}\s+"
        r"판례 검색은 빅케이스\s+"
        r"https://bigcase\.ai/cases/[^\n]+",
        " ",
        value,
    )

    return value.strip()


def extract_pdf_text(pdf_path: Path) -> str:
    """PDF의 모든 페이지에서 텍스트를 추출합니다."""

    reader = PdfReader(str(pdf_path))

    page_texts = [
        page.extract_text() or ""
        for page in reader.pages
    ]

    content = clean_text("\n".join(page_texts))

    if not content:
        raise ValueError(
            f"PDF에서 본문을 추출하지 못했습니다: {pdf_path}"
        )

    return content


def parse_filename(pdf_path: Path) -> dict:
    """
    판례 파일명에서 법원·선고일·사건번호·사건명을 추출합니다.

    파일명 끝에 '판결 사건명'이 있는 형식과
    사건번호만 있는 병합사건 형식을 모두 지원합니다.
    """

    # 확장자를 제외한 파일명만 사용합니다.
    # 예: 서울중앙지방법원 ... 대금반환
    filename_stem = pdf_path.stem.strip()

    match = FILENAME_PATTERN.match(filename_stem)

    if not match:
        raise ValueError(
            "예상한 판례 파일명 형식이 아닙니다: "
            f"{pdf_path.name}"
        )

    values = match.groupdict()

    decided_at = datetime(
        int(values["year"]),
        int(values["month"]),
        int(values["day"]),
    ).date()

    # 선고일 뒤에 나오는 전체 문자열입니다.
    #
    # 일반 판례:
    # 2025가합11696 판결 대금반환
    #
    # 병합 판례:
    # 2025고단5296,2025고단100024(병합),...
    remainder = values["remainder"].strip()

    case_number_part = remainder
    case_name = None

    # "판결 사건명"이 있는 일반 파일명을 처리합니다.
    if " 판결 " in remainder:
        case_number_part, case_name = remainder.split(
            " 판결 ",
            maxsplit=1,
        )

        case_number_part = case_number_part.strip()
        case_name = case_name.strip()

    # 파일명이 "... 사건번호 판결.pdf"로 끝나고
    # 별도의 사건명은 없는 경우를 처리합니다.
    elif remainder.endswith(" 판결"):
        case_number_part = remainder[
            :-len(" 판결")
        ].strip()

    # 대표 사건번호와 병합 사건번호를 모두 추출합니다.
    #
    # 현재 보유 파일에 등장하는 사건번호 유형:
    # 가단, 가합, 나, 다, 노, 두, 고단, 초기
    all_case_numbers = re.findall(
        r"\d{4}(?:"
        r"가단|가합|나|다|노|두|"
        r"고단|고합|초기"
        r")\d+",
        case_number_part,
    )

    if not all_case_numbers:
        raise ValueError(
            f"사건번호를 찾지 못했습니다: {pdf_path.name}"
        )

    # 파일명에 사건명이 없는 병합사건은 임시 명칭을 부여합니다.
    #
    # 실제 판결문 본문에는 사기, 컴퓨터등사용사기,
    # 전자금융거래법위반 등이 표시되어 있지만,
    # 파일명 파싱 단계에서는 임의로 단정하지 않습니다.
    if not case_name:
        case_name = (
            "병합사건"
            if len(all_case_numbers) > 1
            else "사건명 미확인"
        )

    return {
        "court": values["court"].strip(),
        "decided_at": decided_at,

        # DB case_number에는 첫 번째 사건번호를 대표값으로 사용합니다.
        "case_number": all_case_numbers[0],

        # 병합 사건번호 전체는 metadata에 저장됩니다.
        "all_case_numbers": all_case_numbers,

        "case_name": case_name,
    }


def split_sections(content: str):
    """
    MVP용 판결문 구간 분리입니다.

    '주문', '청구취지', '이유' 위치를 이용하지만 PDF별 형식이
    다를 수 있으므로 구간을 찾지 못하면 전체 본문을 reasoning으로
    저장합니다.
    """

    sections = []

    order_match = re.search(
        r"\b주\s*문\b(?P<body>.*?)(?=\b청\s*구\s*취\s*지\b|\b이\s*유\b)",
        content,
        flags=re.DOTALL,
    )

    if order_match:
        order = clean_text(order_match.group("body"))

        if order:
            # 기존 판례 section 모델에 맞추기 위해 주문은 holding으로 저장합니다.
            sections.append(
                NormalizedPrecedentSection(
                    section_type="holding",
                    title="주문",
                    content=order,
                )
            )

    reasoning_match = re.search(
        r"\b이\s*유\b(?P<body>.+)$",
        content,
        flags=re.DOTALL,
    )

    reasoning = (
        clean_text(reasoning_match.group("body"))
        if reasoning_match
        else content
    )

    sections.append(
        NormalizedPrecedentSection(
            section_type="reasoning",
            title="판결이유",
            content=reasoning,
        )
    )

    return sections


def normalize_precedent_pdf(
    pdf_path: Path,
    category: str,
    rag_enabled: bool = True,
) -> NormalizedPrecedent:
    """판례 PDF 하나를 DB 적재 공통 모델로 변환합니다."""

    info = parse_filename(pdf_path)
    extracted_content = extract_pdf_text(pdf_path)
    sections = split_sections(extracted_content)

    full_content = "\n\n".join(
        f"[{section.title}]\n{section.content}"
        for section in sections
    )

    content_hash = hashlib.sha256(
        full_content.encode("utf-8")
    ).hexdigest()

    # PDF 내부에도 같은 URL이 표시되지만, 파일명에서 추출한
    # 법원명과 사건번호로 안정적인 URL을 구성합니다.
    source_url = (
        "https://bigcase.ai/cases/"
        f"{quote(info['court'])}/"
        f"{quote(info['case_number'])}"
    )

    document = NormalizedLegalDocument(
        external_id=(
            f"bigcase-{info['court']}-"
            f"{info['case_number']}"
        ),
        document_type="CASE",
        category=category,
        title=(
            f"{info['case_number']} "
            f"{info['case_name']}"
        ),
        summary=None,
        content=full_content,
        case_number=info["case_number"],
        case_name=info["case_name"],
        court=info["court"],
        decided_at=info["decided_at"],
        judgment_result=None,
        source_name=SOURCE_NAME,
        source_url=source_url,
        source_type="file",
        raw_file=pdf_path.as_posix(),
        content_hash=content_hash,
        metadata={
            "categories": [category],
            "all_case_numbers": info["all_case_numbers"],
            "file_format": "pdf",
            "rag_enabled": rag_enabled,
        },
    )

    return NormalizedPrecedent(
        document=document,
        sections=sections,
    )