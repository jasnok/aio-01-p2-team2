"""
판례 PDF와 API XML의 본문 품질을 전수 검사합니다.

이 스크립트는:
- DB를 변경하지 않습니다.
- 원본 파일을 변경하지 않습니다.
- OpenAI Embedding API를 호출하지 않습니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.normalizers.precedent import (
    normalize_precedent_xml,
)
from database.ingestion.normalizers.precedent_pdf import (
    normalize_precedent_pdf,
)
from database.ingestion.text_quality import (
    inspect_text_quality,
    print_quality_result,
)


CATEGORIES = (
    "housing",
    "labor",
    "consumer",
)

RAW_API_CASE_DIR = (
    PROJECT_ROOT / "database" / "raw" / "api" / "cases"
)

RAW_FILE_CASE_DIR = (
    PROJECT_ROOT / "database" / "raw" / "files"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="판례 원본 본문 품질 전수검사"
    )

    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        help="특정 카테고리만 검사합니다.",
    )

    parser.add_argument(
        "--source",
        choices=("api", "files", "all"),
        default="all",
        help="검사할 원본 종류입니다.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    categories = (
        [args.category]
        if args.category
        else list(CATEGORIES)
    )

    checked_count = 0
    warning_count = 0
    error_count = 0

    for category in categories:
        print()
        print("=" * 70)
        print(f"카테고리: {category}")
        print("=" * 70)

        # ---------------------------------------------
        # PDF 판례 검사
        # ---------------------------------------------
        if args.source in ("files", "all"):
            pdf_directory = (
                RAW_FILE_CASE_DIR / category
            )

            for pdf_path in sorted(
                pdf_directory.glob("*.pdf")
            ):
                try:
                    precedent = normalize_precedent_pdf(
                        pdf_path=pdf_path,
                        category=category,
                    )

                    result = inspect_text_quality(
                        content=precedent.document.content,
                        source=str(pdf_path),
                    )

                    print_quality_result(result)

                    checked_count += 1

                    if not result.passed:
                        warning_count += 1

                except Exception as error:
                    error_count += 1

                    print(
                        f"[추출 실패] {pdf_path.name} / "
                        f"{error}"
                    )

        # ---------------------------------------------
        # 국가법령정보센터 API XML 판례 검사
        # ---------------------------------------------
        if args.source in ("api", "all"):
            xml_directory = (
                RAW_API_CASE_DIR / category
            )

            for xml_path in sorted(
                xml_directory.glob("prec_*.xml")
            ):
                try:
                    precedent = normalize_precedent_xml(
                        xml_path=xml_path,
                        category=category,
                    )

                    result = inspect_text_quality(
                        content=precedent.document.content,
                        source=str(xml_path),
                    )

                    print_quality_result(result)

                    checked_count += 1

                    if not result.passed:
                        warning_count += 1

                except Exception as error:
                    error_count += 1

                    print(
                        f"[파싱 실패] {xml_path.name} / "
                        f"{error}"
                    )

    print()
    print("=" * 70)
    print("전수검사 결과")
    print("=" * 70)
    print(f"검사 원본: {checked_count}건")
    print(f"공백 검토 필요: {warning_count}건")
    print(f"추출·파싱 실패: {error_count}건")

    # 추출·파싱 실패가 있을 때만 실패로 종료합니다.
    if error_count:
        print(
            "추출·파싱 실패가 있으므로 "
            "DB 적재 전에 수정해야 합니다."
        )
        return 1

    # 공백 의심은 검토 경고이므로 정상 종료합니다.
    if warning_count:
        print(
            "공백 의심 문구가 있지만 "
            "추출·파싱 자체는 완료되었습니다."
        )

    return 0

    print("전체 원본의 기본 품질검사가 통과되었습니다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())