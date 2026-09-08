"""국가법령정보센터 현행 법령 XML 정규화 모듈.

책임: 원본 XML에서 법령 기본정보와 실제 조문을 읽어 공통 모델로
변환하고 원문 변경 감지용 SHA-256 해시를 만듭니다.

이 파일에서는 API 호출, DB 저장, OpenAI Embedding을 하지 않습니다.
따라서 수집한 원본만으로 정규화 결과를 반복 검증할 수 있습니다.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from database.ingestion.models import (
    NormalizedLegalDocument,
    NormalizedStatute,
    NormalizedStatuteArticle,
)


SOURCE_NAME = "국가법령정보센터"


def clean_text(value: str | None) -> str:
    """XML의 연속 공백과 줄바꿈을 하나의 공백으로 정리합니다."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def element_text(element: ET.Element | None) -> str:
    """항·호·목 등 하위 태그를 포함한 모든 텍스트를 합칩니다."""
    if element is None:
        return ""
    return clean_text(" ".join(element.itertext()))


def parse_date(value: str | None):
    """국가법령정보의 YYYYMMDD 문자열을 date로 변환합니다."""
    value = clean_text(value)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def display_article_number(number: str, branch_number: str) -> str:
    """조문번호와 가지번호를 제N조/제N조의M 형식으로 만듭니다."""
    base = number if number.startswith("제") else f"제{number}조"
    if branch_number and branch_number != "0":
        return f"{base}의{branch_number}"
    return base


def parse_articles(root: ET.Element) -> list[NormalizedStatuteArticle]:
    """목차용 '전문'을 제외하고 실제 '조문'만 추출합니다.

    조문단위의 메타데이터까지 본문에 섞이지 않도록 조문내용·항내용·
    호내용·목내용만 XML 순서대로 선택합니다.
    """
    articles: list[NormalizedStatuteArticle] = []

    for element in root.findall("./조문/조문단위"):
        if element_text(element.find("조문여부")) != "조문":
            continue

        number = element_text(element.find("조문번호"))
        branch_number = element_text(element.find("조문가지번호"))
        title = element_text(element.find("조문제목"))
        content_parts = [
            element_text(child)
            for child in element.iter()
            if child.tag in {"조문내용", "항내용", "호내용", "목내용"}
            and element_text(child)
        ]
        content = clean_text(" ".join(content_parts))
        if not number or not content:
            continue

        articles.append(
            NormalizedStatuteArticle(
                article_key=element.get("조문키"),
                article_number=display_article_number(number, branch_number),
                article_title=title or None,
                content=content,
                metadata={
                    "article_effective_date": element_text(
                        element.find("조문시행일자")
                    ),
                    "article_changed": element_text(
                        element.find("조문변경여부")
                    ),
                },
            )
        )

    if not articles:
        raise ValueError("법령 XML에서 실제 조문을 찾지 못했습니다.")
    return articles


def normalize_statute_xml(
    xml_path: Path,
    category: str,
    categories: list[str] | None = None,
) -> NormalizedStatute:
    """원본 XML 하나를 법령 문서 한 건과 조문 목록으로 변환합니다."""
    root = ET.parse(xml_path).getroot()
    basic = root.find("./기본정보")
    if basic is None:
        raise ValueError(f"법령 기본정보가 없습니다: {xml_path}")

    law_name = element_text(basic.find("법령명_한글"))
    law_id = element_text(basic.find("법령ID"))
    effective_date_text = element_text(basic.find("시행일자"))
    promulgation_date = element_text(basic.find("공포일자"))
    promulgation_number = element_text(basic.find("공포번호"))
    ministry = element_text(basic.find("소관부처"))
    revision_type = element_text(basic.find("제개정구분"))

    if not law_name or not law_id:
        raise ValueError(f"법령명 또는 법령 ID가 없습니다: {xml_path}")

    articles = parse_articles(root)
    full_content = "\n\n".join(
        f"{a.article_number} {a.article_title or ''}\n{a.content}".strip()
        for a in articles
    )
    content_hash = hashlib.sha256(full_content.encode("utf-8")).hexdigest()
    all_categories = categories or [category]

    document = NormalizedLegalDocument(
        external_id=f"law-{law_id}",
        document_type="LAW",
        category=category,
        title=law_name,
        summary=f"{law_name} 현행 법령 조문",
        content=full_content,
        law_name=law_name,
        source_name=SOURCE_NAME,
        # OC는 비밀값이므로 사용자에게 표시할 출처 URL에 넣지 않습니다.
        source_url=f"https://www.law.go.kr/법령/{quote(law_name)}",
        # 원천이 API이므로 로컬 XML에서 읽어도 source_type은 api입니다.
        source_type="api",
        raw_file=xml_path.as_posix(),
        effective_date=parse_date(effective_date_text),
        source_updated_at=None,
        content_hash=content_hash,
        metadata={
            "law_id": law_id,
            "law_key": root.get("법령키"),
            # 민법은 한 번 저장하되 housing/consumer 양쪽에서 찾습니다.
            "categories": all_categories,
            "promulgation_date": promulgation_date,
            "promulgation_number": promulgation_number,
            "ministry_name": ministry,
            "revision_type": revision_type,
            "article_count": len(articles),
        },
    )
    return NormalizedStatute(document=document, articles=articles)
