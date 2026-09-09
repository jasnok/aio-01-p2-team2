"""
RAG에 저장하거나 임베딩하기 전 본문 품질을 검사합니다.

주의:
- 이 모듈은 한글 공백을 자동 삭제하지 않습니다.
- 정상적인 띄어쓰기까지 훼손할 수 있으므로 의심 구간만 탐지합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# 예:
# 앞 서 본 인 정 사 실
# 손 해 배 상 청 구
#
# 한글 한 음절이 공백으로 4개 이상 연속 분리된 경우를
# PDF 추출 오류 의심 패턴으로 판단합니다.
SPACED_HANGUL_PATTERN = re.compile(
    r"(?<![가-힣])"
    r"(?:[가-힣][ \t]+){3,}"
    r"[가-힣]"
    r"(?![가-힣])"
)


@dataclass
class TextQualityResult:
    """본문 하나의 품질검사 결과입니다."""

    source: str
    content_length: int
    suspicious_count: int
    samples: list[str]

    @property
    def passed(self) -> bool:
        return self.suspicious_count == 0


def inspect_text_quality(
    content: str,
    source: str,
    sample_limit: int = 5,
) -> TextQualityResult:
    """
    음절 단위 공백 오류가 의심되는 구간을 검사합니다.

    주의:
    - 의심 문구를 자동 수정하지 않습니다.
    - 정상적인 문장이나 표도 탐지될 수 있습니다.
    - 최종 차단 여부는 validate_embedding_text()가 결정합니다.
    """

    matches = [
        match.group(0).strip()
        for match in SPACED_HANGUL_PATTERN.finditer(content)
    ]

    # 같은 문구가 반복될 수 있으므로
    # 출력 샘플만 중복 제거합니다.
    unique_samples = list(
        dict.fromkeys(matches)
    )

    return TextQualityResult(
        source=source,
        content_length=len(content),
        suspicious_count=len(matches),
        samples=unique_samples[:sample_limit],
    )

def print_quality_result(
    result: TextQualityResult,
) -> None:
    """검사 결과를 콘솔에 출력합니다."""

    status = "정상" if result.passed else "검토 필요"

    print(
        f"[{status}] {result.source} / "
        f"본문 길이={result.content_length} / "
        f"공백 의심={result.suspicious_count}"
    )

    for sample in result.samples:
        print(f"  - 의심 문구: {sample}")


def validate_embedding_text(
    content: str,
    source: str,
) -> None:
    """
    임베딩 불가능한 심각한 본문 오류만 차단합니다.

    한글 공백 의심 패턴은 정상 문장이나 표에서도 발생할 수 있으므로
    경고만 출력하고 임베딩을 중단하지 않습니다.
    """

    if not content or not content.strip():
        raise ValueError(
            f"임베딩할 본문이 비어 있습니다: {source}"
        )

    # 너무 짧은 청크는 판례 검색에 활용하기 어렵습니다.
    if len(content.strip()) < 30:
        raise ValueError(
            "임베딩할 본문이 지나치게 짧습니다: "
            f"{source} / 길이={len(content.strip())}"
        )

    # PDF 문자 디코딩에 실패할 때 나타날 수 있는 대체문자입니다.
    replacement_character_count = content.count("\ufffd")

    if replacement_character_count >= 3:
        raise ValueError(
            "본문에서 문자 디코딩 오류가 발견되었습니다: "
            f"{source} / "
            f"대체문자={replacement_character_count}개"
        )

    result = inspect_text_quality(
        content=content,
        source=source,
    )

    # 한글 공백 의심 문구는 오류가 아닌 경고로 취급합니다.
    if not result.passed:
        samples = " | ".join(result.samples)

        print(
            "[품질 경고] 한글 음절 공백을 확인하세요: "
            f"{source} / "
            f"의심 구간={result.suspicious_count} / "
            f"샘플={samples}"
        )