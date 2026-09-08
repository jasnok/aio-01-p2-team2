"""국가법령정보센터 판례 상세 XML 정규화 모듈입니다."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from database.ingestion.models import (
    NormalizedLegalDocument,
    NormalizedPrecedent,
    NormalizedPrecedentSection,
)


SOURCE_NAME = "국가법령정보센터"


def clean_text(value: str | None) -> str:
    """
    CDATA 안의 br 태그, HTML Entity와 연속 공백을 정리합니다.
    """

    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in value.splitlines()
    ]

    return "\n".join(
        line
        for line in lines
        if line
    )


def element_text(
    root: ET.Element,
    tag: str,
) -> str:
    """XML 태그 하나의 본문을 안전하게 반환합니다."""

    element = root.find(tag)

    if element is None:
        return ""

    return clean_text(
        "".join(element.itertext())
    )


def parse_date(value: str):
    """YYYYMMDD 형식의 선고일자를 date로 변환합니다."""

    value = value.strip()

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y%m%d",
        ).date()
    except ValueError:
        return None


def normalize_precedent_xml(
    xml_path: Path,
    category: str,
) -> NormalizedPrecedent:
    """판례 상세 XML 하나를 공통 판례 모델로 변환합니다."""

    root = ET.parse(xml_path).getroot()

    precedent_id = element_text(
        root,
        "판례정보일련번호",
    )

    case_name = element_text(root, "사건명")
    case_number = element_text(root, "사건번호")
    decided_at_text = element_text(root, "선고일자")
    court = element_text(root, "법원명")
    judgment_result = element_text(root, "선고")
    case_type = element_text(root, "사건종류명")
    judgment_type = element_text(root, "판결유형")

    holding = element_text(root, "판시사항")
    summary = element_text(root, "판결요지")
    reference_law = element_text(root, "참조조문")
    reference_case = element_text(root, "참조판례")
    reasoning = element_text(root, "판례내용")

    if not precedent_id:
        raise ValueError(
            f"판례일련번호가 없습니다: {xml_path}"
        )

    if not case_name or not case_number:
        raise ValueError(
            f"사건명 또는 사건번호가 없습니다: {xml_path}"
        )

    sections: list[NormalizedPrecedentSection] = []

    section_values = [
        ("holding", "판시사항", holding),
        ("summary", "판결요지", summary),
        ("reference_law", "참조조문", reference_law),
        ("reference_case", "참조판례", reference_case),
        ("reasoning", "판례내용", reasoning),
    ]

    for section_type, title, content in section_values:
        if not content:
            continue

        sections.append(
            NormalizedPrecedentSection(
                section_type=section_type,
                title=title,
                content=content,
            )
        )

    if not sections:
        raise ValueError(
            f"판례 본문이 없습니다: {xml_path}"
        )

    # legal_documents.content에 저장할 판례 전체 본문입니다.
    full_content = "\n\n".join(
        f"[{section.title}]\n{section.content}"
        for section in sections
    )

    content_hash = hashlib.sha256(
        full_content.encode("utf-8")
    ).hexdigest()

    source_url = (
        "https://www.law.go.kr/LSW/precInfoP.do?"
        + urlencode({"precSeq": precedent_id})
    )

    document = NormalizedLegalDocument(
        external_id=f"prec-{precedent_id}",
        document_type="CASE",
        category=category,
        title=case_name,
        summary=summary or holding or None,
        content=full_content,
        law_name=None,
        article_number=None,
        case_number=case_number,
        case_name=case_name,
        court=court or None,
        decided_at=parse_date(decided_at_text),
        judgment_result=judgment_result or None,
        source_name=SOURCE_NAME,
        source_url=source_url,
        source_type="api",
        raw_file=xml_path.as_posix(),
        content_hash=content_hash,
        metadata={
            "precedent_id": precedent_id,
            "case_type": case_type,
            "judgment_type": judgment_type,
            "reference_law": reference_law,
            "reference_case": reference_case,
            "categories": [category],
        },
    )

    return NormalizedPrecedent(
        document=document,
        sections=sections,
    )