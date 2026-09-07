"""
MVP 대상 현행 법령을 국가법령정보 공동활용 API에서 한 번 수집한다.

실행 위치:
    database/

실행 명령:
    python scripts/collect_laws_once.py

주의:
- 이 스크립트는 PostgreSQL에 데이터를 넣지 않는다.
- 원본 XML 파일만 database/raw/api/laws에 저장한다.
- 이미 파일이 있으면 기본적으로 다시 내려받지 않는다.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import httpx
from dotenv import load_dotenv


# database/.env를 명시적으로 읽는다.
DATABASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = DATABASE_DIR / ".env"

# 원본 법령 XML 저장 위치
OUTPUT_DIR = DATABASE_DIR / "raw" / "api" / "laws"

# 프로젝트에서 우선 수집할 현행 법령
TARGET_LAWS = [
    {
        "name": "민법",
        "filename": "민법.xml",
        "categories": ["housing", "consumer"],
    },
    {
        "name": "주택임대차보호법",
        "filename": "주택임대차보호법.xml",
        "categories": ["housing"],
    },
    {
        "name": "근로기준법",
        "filename": "근로기준법.xml",
        "categories": ["labor"],
    },
    {
        "name": "근로자퇴직급여 보장법",
        "filename": "근로자퇴직급여_보장법.xml",
        "categories": ["labor"],
    },
    {
        "name": "전자상거래 등에서의 소비자보호에 관한 법률",
        "filename": "전자상거래법.xml",
        "categories": ["consumer"],
    },
    {
        "name": "소비자기본법",
        "filename": "소비자기본법.xml",
        "categories": ["consumer"],
    },
]


def normalized_text(value: str | None) -> str:
    """법령명의 공백과 HTML 태그를 제거하여 비교한다."""
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", "", value).strip()


def find_exact_law(xml_content: bytes, requested_name: str) -> dict[str, str]:
    """
    목록 XML에서 법령명이 정확히 일치하는 항목을 찾는다.

    목록 조회에는 시행령·시행규칙 등이 함께 반환될 수 있으므로
    첫 번째 결과를 무조건 선택하면 안 된다.
    """
    root = ElementTree.fromstring(xml_content)
    expected = normalized_text(requested_name)

    for element in root.iter():
        children = {child.tag: (child.text or "").strip() for child in element}

        law_name = children.get("법령명한글", "")
        law_id = children.get("법령ID", "")
        law_mst = children.get("법령일련번호", "")

        if normalized_text(law_name) == expected and law_id:
            return {
                "law_name": law_name,
                "law_id": law_id,
                "law_mst": law_mst,
                "effective_date": children.get("시행일자", ""),
                "detail_link": children.get("법령상세링크", ""),
            }

    raise RuntimeError(
        f"목록 응답에서 정확히 일치하는 법령을 찾지 못했습니다: {requested_name}"
    )


def main() -> None:
    load_dotenv(ENV_PATH)

    base_url = os.getenv("LAW_API_BASE_URL", "").rstrip("/")
    oc = os.getenv("LAW_API_OC", "").strip()
    timeout = float(os.getenv("LAW_API_TIMEOUT_SECONDS", "20"))

    if not base_url:
        raise RuntimeError("database/.env의 LAW_API_BASE_URL을 확인하세요.")

    if not oc or oc == "실제_OC_인증값":
        raise RuntimeError("database/.env의 LAW_API_OC를 확인하세요.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for target in TARGET_LAWS:
            law_name = target["name"]
            output_path = OUTPUT_DIR / target["filename"]

            print(f"\n[{law_name}]")

            # 기존 원본 파일이 있으면 다시 호출하지 않는다.
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"SKIP: 이미 존재함 -> {output_path.name}")

                manifest.append(
                    {
                        "law_name": law_name,
                        "categories": target["categories"],
                        "filename": target["filename"],
                        "status": "existing",
                    }
                )
                continue

            # 1. 법령명으로 현행 법령 목록을 검색한다.
            list_response = client.get(
                f"{base_url}/lawSearch.do",
                params={
                    "OC": oc,
                    "target": "law",
                    "type": "XML",
                    "search": 1,
                    "query": law_name,
                    "display": 100,
                    "page": 1,
                },
            )
            list_response.raise_for_status()

            # 2. 법령명이 정확히 일치하는 법령 ID를 찾는다.
            law_info = find_exact_law(list_response.content, law_name)

            print(f"법령 ID: {law_info['law_id']}")
            print(f"법령일련번호: {law_info['law_mst']}")

            # 3. 확인한 법령 ID로 현행 법령 본문을 조회한다.
            detail_response = client.get(
                f"{base_url}/lawService.do",
                params={
                    "OC": oc,
                    "target": "law",
                    "type": "XML",
                    "ID": law_info["law_id"],
                },
            )
            detail_response.raise_for_status()

            # HTML 오류 페이지가 저장되는 것을 방지한다.
            content_type = detail_response.headers.get("content-type", "")
            response_head = detail_response.content[:200].lower()

            if b"<html" in response_head:
                raise RuntimeError(
                    f"{law_name} 본문 조회 결과가 XML이 아닌 HTML입니다. "
                    "OC 인증값과 법령 API 승인 상태를 확인하세요."
                )

            if not detail_response.content.strip():
                raise RuntimeError(f"{law_name} 본문 응답이 비어 있습니다.")

            # 4. API 원본 XML을 수정하지 않고 그대로 저장한다.
            output_path.write_bytes(detail_response.content)

            print(
                f"SAVED: {output_path.name} "
                f"({len(detail_response.content):,} bytes)"
            )

            manifest.append(
                {
                    "law_name": law_info["law_name"],
                    "law_id": law_info["law_id"],
                    "law_mst": law_info["law_mst"],
                    "effective_date": law_info["effective_date"],
                    "categories": target["categories"],
                    "filename": target["filename"],
                    "source": "국가법령정보센터",
                    "status": "downloaded",
                }
            )

    # OC 인증값은 manifest에 절대 기록하지 않는다.
    manifest_path = OUTPUT_DIR / "collection_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "documents": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n수집 작업 완료")
    print(f"원본 위치: {OUTPUT_DIR}")
    print(f"수집 명세: {manifest_path}")


if __name__ == "__main__":
    main()