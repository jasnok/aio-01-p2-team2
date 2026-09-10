"""
빅케이스에서 내려받은 판례 PDF를 공통 판례 모델로 변환합니다.

처리 내용:
1. 파일명에서 법원명·선고일·사건번호·사건명 추출
2. pdfplumber로 PDF 본문 추출
3. 반복 안내문과 불필요한 공백 정리
4. 주문·판결이유 구간 분리
5. NormalizedPrecedent 모델 생성

주의:
- source_name은 판결 법원이 아니라 PDF 제공 서비스인 빅케이스입니다.
- 실제 판결 법원은 legal_documents.court에 저장합니다.
- source_type은 API 응답이 아니라 직접 확보한 파일이므로 file입니다.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pdfplumber

from database.ingestion.models import (
    NormalizedLegalDocument,
    NormalizedPrecedent,
    NormalizedPrecedentSection,
)


# ---------------------------------------------------------
# 출처
# ---------------------------------------------------------

SOURCE_NAME = "빅케이스"


# ---------------------------------------------------------
# 파일명 형식
# ---------------------------------------------------------

# 지원 예시:
#
# 서울중앙지방법원 2026. 7. 16. 선고
# 2025가합11696 판결 대금반환.pdf
#
# 서울중앙지방법원 2026. 7. 14. 선고
# 2025고단5296 판결 사기등병합.pdf
#
# 서울지방법원 2003. 7. 14. 선고
# 2002가합75662,2003가합11771 판결 채무부존재확인.pdf
#
# 이 정규식에서는 법원명·선고일과 그 뒤의 나머지 문자열만
# 추출합니다. 구체적인 사건번호는 parse_filename()에서
# 별도의 정규식으로 처리합니다.
FILENAME_PATTERN = re.compile(
    r"^(?P<court>.+?)\s+"
    r"(?P<year>\d{4})\.\s*"
    r"(?P<month>\d{1,2})\.\s*"
    r"(?P<day>\d{1,2})\.\s*"
    r"선고\s+"
    r"(?P<remainder>.+)$"
)


# 현재 확보한 PDF에서 사용하는 사건번호 유형입니다.
#
# 예:
# 2026가단806
# 2025가합11696
# 2025나208119
# 2025다217842
# 2026노670
# 2017도17611
# 2025두34604
# 2025고단5296
# 2025고합100
# 2025초기5772
CASE_NUMBER_PATTERN = re.compile(
    r"\d{4}(?:"
    r"가단|가합|가소|"
    r"나|다|"
    r"노|도|두|"
    r"고단|고합|"
    r"초기"
    r")\d+"
)


# ---------------------------------------------------------
# 일반 텍스트 정리
# ---------------------------------------------------------

def clean_text(value: str | None) -> str:
    """
    PDF에서 추출한 문자열을 정리합니다.

    여기에서는 다음 항목만 처리합니다.

    - NULL 문자 제거
    - 탭과 연속된 공백 정리
    - 과도한 빈 줄 정리
    - 페이지마다 반복되는 빅케이스 안내문 제거

    한글 사이의 모든 공백을 강제로 삭제하면 정상적인 단어
    경계도 사라지므로 한글 공백 제거 정규식은 사용하지 않습니다.
    """

    if not value:
        return ""

    value = value.replace("\x00", " ")

    # 탭 또는 두 칸 이상의 공백을 한 칸으로 변경합니다.
    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    # 페이지마다 반복되는 날짜·빅케이스 출처 안내를 제거합니다.
    value = re.sub(
        r"\d{4}-\d{2}-\d{2}\s+"
        r"판례\s*검색은\s*빅케이스\s*"
        r"https://bigcase\.ai/cases/[^\n]+",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # 페이지 표기 예:
    # 1 / 18
    # 12 / 24
    value = re.sub(
        r"(?m)^\s*\d+\s*/\s*\d+\s*$",
        " ",
        value,
    )

    # 빈 줄이 세 개 이상 반복되면 두 줄로 정리합니다.
    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    # 줄마다 앞뒤 공백을 제거합니다.
    lines = [
        line.strip()
        for line in value.splitlines()
    ]

    return "\n".join(
        line
        for line in lines
        if line
    ).strip()


# ---------------------------------------------------------
# PDF 본문 추출
# ---------------------------------------------------------

def extract_pdf_text(
    pdf_path: Path,
) -> str:
    """
    PDF의 모든 페이지에서 판결문 텍스트를 추출합니다.

    pypdf는 일부 빅케이스 PDF에서 다음과 같이 한글 음절 사이에
    불필요한 공백을 넣었습니다.

        앞 서 본 인 정 사 실

    pdfplumber에서 x_tolerance=2를 사용했을 때 다음과 같이
    정상적인 단어 경계로 추출되는 것을 확인했습니다.

        앞서 본 인정사실

    PDF 페이지에 텍스트가 없으면 해당 페이지를 빈 문자열로
    처리하되, PDF 전체가 비어 있으면 오류로 중단합니다.
    """

    page_texts: list[str] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(
                pdf.pages,
                start=1,
            ):
                page_text = page.extract_text(
                    x_tolerance=2,
                    y_tolerance=3,
                )

                if not page_text:
                    print(
                        "PDF 텍스트가 없는 페이지: "
                        f"{pdf_path.name} / "
                        f"{page_number}페이지"
                    )

                    page_text = ""

                page_texts.append(page_text)

    except Exception as error:
        raise ValueError(
            "PDF 파일을 읽는 중 오류가 발생했습니다: "
            f"{pdf_path} / {error}"
        ) from error

    content = clean_text(
        "\n".join(page_texts)
    )

    if not content:
        raise ValueError(
            "PDF에서 본문을 추출하지 못했습니다: "
            f"{pdf_path}"
        )

    return content


# ---------------------------------------------------------
# 파일명 분석
# ---------------------------------------------------------

def parse_filename(
    pdf_path: Path,
) -> dict:
    """
    파일명에서 판례 메타데이터를 추출합니다.

    반환값:
    - court: 법원명
    - decided_at: 선고일
    - case_number: 대표 사건번호
    - all_case_numbers: 병합사건을 포함한 전체 사건번호
    - case_name: 사건명

    병합사건에서는 첫 번째 사건번호를 대표번호로 사용하고
    전체 사건번호를 metadata.all_case_numbers에 저장합니다.
    """

    filename_stem = pdf_path.stem.strip()

    # 전체 파일명 형식과 일치하는지 확인합니다.
    # match() 대신 fullmatch()를 사용해 일부 문자열만 우연히
    # 일치하는 상황을 방지합니다.
    match = FILENAME_PATTERN.fullmatch(
        filename_stem
    )

    if not match:
        raise ValueError(
            "예상한 판례 파일명 형식이 아닙니다: "
            f"{pdf_path.name}"
        )

    values = match.groupdict()

    # 정규식 그룹이 비어 있는 경우 명확한 오류를 발생시킵니다.
    required_groups = (
        "court",
        "year",
        "month",
        "day",
        "remainder",
    )

    missing_groups = [
        group_name
        for group_name in required_groups
        if not values.get(group_name)
    ]

    if missing_groups:
        raise ValueError(
            "파일명에서 필수값을 추출하지 못했습니다: "
            f"{pdf_path.name} / "
            f"누락={missing_groups}"
        )

    try:
        decided_at = datetime(
            int(values["year"]),
            int(values["month"]),
            int(values["day"]),
        ).date()

    except ValueError as error:
        raise ValueError(
            "파일명의 선고일이 올바르지 않습니다: "
            f"{pdf_path.name}"
        ) from error

    # '선고' 다음에 나오는 사건번호·판결·사건명 부분입니다.
    remainder = values["remainder"].strip()

    case_number_part = remainder
    case_name: str | None = None

    # 일반적인 파일명:
    # 2025가합11696 판결 대금반환
    if " 판결 " in remainder:
        case_number_part, case_name = remainder.split(
            " 판결 ",
            maxsplit=1,
        )

        case_number_part = (
            case_number_part.strip()
        )

        case_name = case_name.strip()

    # 사건명 없이 '판결'로 끝나는 파일:
    # 2025가합11696 판결
    elif remainder.endswith(" 판결"):
        case_number_part = remainder[
            :-len(" 판결")
        ].strip()

    # 사건번호를 모두 추출합니다.
    all_case_numbers = (
        CASE_NUMBER_PATTERN.findall(
            case_number_part
        )
    )

    if not all_case_numbers:
        raise ValueError(
            "사건번호를 찾지 못했습니다: "
            f"{pdf_path.name}"
        )

    # 사건명이 파일명에 없는 경우 임시 명칭을 부여합니다.
    if not case_name:
        if len(all_case_numbers) > 1:
            case_name = "병합사건"
        else:
            case_name = "사건명 미확인"

    return {
        "court": values["court"].strip(),
        "decided_at": decided_at,

        # 첫 사건번호를 DB 대표 사건번호로 사용합니다.
        "case_number": all_case_numbers[0],

        # 병합사건 전체 번호는 JSONB metadata에 보관합니다.
        "all_case_numbers": all_case_numbers,

        "case_name": case_name,
    }


# ---------------------------------------------------------
# 판결문 구간 분리
# ---------------------------------------------------------

def split_sections(
    content: str,
) -> list[NormalizedPrecedentSection]:
    """
    판결문 본문을 주문과 판결이유로 분리합니다.

    PDF마다 '주문', '청구취지', '이유' 표기가 다를 수 있으므로
    공백을 허용하는 정규식을 사용합니다.

    구간을 찾지 못하면 전체 본문을 판결이유로 저장합니다.
    """

    sections: list[
        NormalizedPrecedentSection
    ] = []

    # 주문부터 청구취지 또는 이유 전까지 추출합니다.
    order_match = re.search(
        r"\b주\s*문\b"
        r"(?P<body>.*?)"
        r"(?="
        r"\b청\s*구\s*취\s*지\b"
        r"|"
        r"\b이\s*유\b"
        r")",
        content,
        flags=re.DOTALL,
    )

    if order_match:
        order = clean_text(
            order_match.group("body")
        )

        if order:
            # 기존 모델의 section_type 선택값에 맞춰
            # 주문은 holding으로 저장합니다.
            sections.append(
                NormalizedPrecedentSection(
                    section_type="holding",
                    title="주문",
                    content=order,
                )
            )

    # 이유부터 문서 끝까지 추출합니다.
    reasoning_match = re.search(
        r"\b이\s*유\b"
        r"(?P<body>.+)$",
        content,
        flags=re.DOTALL,
    )

    if reasoning_match:
        reasoning = clean_text(
            reasoning_match.group("body")
        )
    else:
        # 이유 구간을 찾지 못한 PDF는 전체 본문을 사용합니다.
        reasoning = content

    if reasoning:
        sections.append(
            NormalizedPrecedentSection(
                section_type="reasoning",
                title="판결이유",
                content=reasoning,
            )
        )

    if not sections:
        raise ValueError(
            "판결문에서 저장할 본문 구간을 "
            "생성하지 못했습니다."
        )

    return sections


# ---------------------------------------------------------
# 공통 판례 모델 생성
# ---------------------------------------------------------

def normalize_precedent_pdf(
    pdf_path: Path,
    category: str,
    rag_enabled: bool = True,
) -> NormalizedPrecedent:
    """
    판례 PDF 하나를 공통 판례 모델로 변환합니다.

    처리 결과:
    - legal_documents에 저장할 문서
    - legal_chunks 생성에 사용할 판례 Section 목록
    """

    if category not in (
        "housing",
        "labor",
        "consumer",
    ):
        raise ValueError(
            f"지원하지 않는 category입니다: {category}"
        )

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"판례 PDF가 없습니다: {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"PDF 파일이 아닙니다: {pdf_path}"
        )

    # 파일명에서 법원·선고일·사건번호를 추출합니다.
    info = parse_filename(pdf_path)

    # pdfplumber로 원문을 추출합니다.
    extracted_content = extract_pdf_text(
        pdf_path
    )

    # 주문과 판결이유로 구분합니다.
    sections = split_sections(
        extracted_content
    )

    # legal_documents.content에 저장할 전체 본문입니다.
    full_content = "\n\n".join(
        f"[{section.title}]\n{section.content}"
        for section in sections
    )

    content_hash = hashlib.sha256(
        full_content.encode("utf-8")
    ).hexdigest()

    # PDF에 표시된 빅케이스 개별 판례 주소 형식입니다.
    source_url = (
        "https://bigcase.ai/cases/"
        f"{quote(info['court'])}/"
        f"{quote(info['case_number'])}"
    )

    document = NormalizedLegalDocument(
        external_id=(
            f"bigcase-"
            f"{info['court']}-"
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

        # 판례 문서이므로 법령 전용 필드는 비웁니다.
        law_name=None,
        article_number=None,

        case_number=info["case_number"],
        case_name=info["case_name"],
        court=info["court"],
        decided_at=info["decided_at"],
        judgment_result=None,

        source_name=SOURCE_NAME,
        source_url=source_url,
        source_type="file",
        raw_file=pdf_path.as_posix(),

        effective_date=None,
        source_updated_at=None,

        content_hash=content_hash,

        metadata={
            "categories": [category],
            "all_case_numbers": (
                info["all_case_numbers"]
            ),
            "file_format": "pdf",
            "rag_enabled": rag_enabled,
            "text_extractor": "pdfplumber",
            "text_extractor_options": {
                "x_tolerance": 2,
                "y_tolerance": 3,
            },
        },
    )

    return NormalizedPrecedent(
        document=document,
        sections=sections,
    )