"""선정된 판례 상세 XML을 카테고리별로 1회 수집합니다."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.ingestion.collectors.precedent_open_api import (
    save_precedent_xml,
)


RAW_CASE_DIR = (
    PROJECT_ROOT
    / "database"
    / "raw"
    / "api"
    / "cases"
)


# 판례일련번호가 공식 상세 페이지에서 확인된 판례입니다.
CASE_TARGETS = {
    "housing": [
        "211709",
        "193797",
        "605771",
        "239521",
        "194367",
    ],
    "labor": [
        "205749",
        "235959",
        "194093",
        "615691",
        "618511",
    ],

    # Consumer는 현재 판례일련번호 확인 작업이 남았습니다.
    # 사건번호 2004다54633, 2000다8397의 ID를 확인한 후 넣습니다.
    "consumer": [
        # "판례일련번호",
    ],
}


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(
        PROJECT_ROOT / "database" / ".env",
        override=True,
    )

    collected_count = 0

    for category, precedent_ids in CASE_TARGETS.items():
        for precedent_id in precedent_ids:
            output_path = (
                RAW_CASE_DIR
                / category
                / f"prec_{precedent_id}.xml"
            )

            if output_path.exists():
                print(f"이미 존재하여 건너뜀: {output_path}")
                continue

            saved_path = save_precedent_xml(
                precedent_id=precedent_id,
                output_path=output_path,
            )

            print(f"저장 완료: {saved_path}")
            collected_count += 1

    print(f"신규 수집 판례 수: {collected_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())