# Database scripts

이 폴더에는 다음 명령의 진입점을 구현합니다.

- `migrate.py`: Migration 실행
- `ingest.py`: 승인된 Open API 수집 실행
- `seed.py`: 공식 출처가 확인된 평가용 Seed 적재

스크립트는 import 시 자동 실행하지 않고 `if __name__ == "__main__"` 진입점을 사용합니다.
