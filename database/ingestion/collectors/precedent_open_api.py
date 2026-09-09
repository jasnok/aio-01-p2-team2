"""
국가법령정보센터 판례 상세 XML 수집기입니다.
이 파일은 API 호출과 원본 저장만 담당합니다. DB 적재나 임베딩은 하지 않습니다.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx


def fetch_precedent_xml(
    precedent_id: str,
) -> bytes:
    """
    판례일련번호를 이용하여 판례 상세 XML을 가져옵니다.

    precedent_id 예:
    193797
    """

    base_url = os.getenv(
        "LAW_API_BASE_URL",
        "https://www.law.go.kr/DRF",
    )

    oc = os.getenv("LAW_API_OC")

    if not oc:
        raise RuntimeError(
            "LAW_API_OC 환경변수가 없습니다."
        )

    timeout_seconds = float(
        os.getenv(
            "LAW_API_TIMEOUT_SECONDS",
            "20",
        )
    )

    response = httpx.get(
        f"{base_url.rstrip('/')}/lawService.do",
        params={
            "OC": oc,
            "target": "prec",
            "ID": precedent_id,
            "type": "XML",
        },
        timeout=timeout_seconds,
    )

    response.raise_for_status()

    content = response.content

    # HTML 오류 응답이나 비어 있는 응답을 저장하지 않습니다.
    if not content:
        raise ValueError(
            f"판례 응답이 비어 있습니다: {precedent_id}"
        )

    if b"<PrecService" not in content:
        preview = content[:300].decode(
            "utf-8",
            errors="replace",
        )

        raise ValueError(
            f"정상적인 판례 XML이 아닙니다: "
            f"{precedent_id}\n{preview}"
        )

    return content


def save_precedent_xml(
    precedent_id: str,
    output_path: Path,
) -> Path:
    """판례 상세 XML을 지정된 원본 경로에 저장합니다."""

    content = fetch_precedent_xml(precedent_id)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_bytes(content)

    return output_path