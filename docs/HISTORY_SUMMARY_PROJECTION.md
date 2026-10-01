# 이력 목록의 요약 필드 조회

## 변경

이력 목록의 전체 답변 snapshot 대신 payload의 question_summary와 answer만 조회한다.
Python 요약의 기존 fallback 규칙과 300자 제한은 유지한다. 원본 snapshot을 DB에서
변경하지 않고 상세 복원은 전체 snapshot을 반환한다. 일반 분석·용어 설명의 목록
형식, 소유자 필터, 페이지 순서도 유지한다.

## 실제 로컬 PostgreSQL 측정

PostgreSQL 16.15 임시 테이블, 합성 이력별 사용하지 않는 payload 64KB.
페이지 크기 20, 각 경로 준비 조회 후 순서를 번갈아 20회 측정했다.

| 전체 이력 수 | 반환 행 | 전체 / 투영 직렬화 크기(byte) | 전체 / 투영 조회 중앙값(ms) |
|---:|---:|---:|---:|
| 10 | 10 | 659,296 / 3,506 | 10.753 / 3.123 |
| 1,000 | 20 | 1,318,826 / 7,246 | 20.608 / 4.678 |

공개 목록 결과는 두 경로에서 동일했다. 시간은 COUNT와 목록 SQL 및 행 변환의 경과
시간이며 공개 요약 구성·직렬화·HTTP·LLM을 제외한다. 크기는 저장소 반환 결과의 JSON
직렬화 크기이며 DB wire 전송량 자체가 아니다. 로컬 부하와 캐시에 따라 편차가 있으며
전체 사이트 개선률이나 운영 환경의 일정한 지연을 보장하지 않는다.

[원본 JSON](../output/history/history-projection-benchmark.json)에 샘플과 저장소·비교 SQL
SHA256을 보관했다. 비교 SQL은 현재 쿼리에서 snapshot 투영 부분만 이전 전체 조회로
되돌려 구성하며 준비 조회 전에 생성·캐시하여 생성 비용이 측정에 반복 포함되지 않는다.

## 검증

실제 PostgreSQL에서 분석/용어 이력, NULL snapshot, payload 누락·NULL·배열·문자열,
빈 요약 fallback, boolean 및 객체 legacy 값, 긴 답변의 공개 목록 결과 동등성을 검증했다.
전체 상세 snapshot 보존, 소유자 격리, 빈 메시지, 페이지 순서·총개수도 확인했다.
테스트의 빈 메시지 기대값을 분석 분야에 맞추어 수정한 뒤 전체 회귀 테스트를 통과했다.

## 재현과 한계

테스트 PostgreSQL URL을 RUN_POSTGRES_INTEGRATION으로 설정한 뒤 실행한다:

```powershell
python -m scripts.benchmark_history_projection --output output/history/history-projection-benchmark.json
```

pg_temp 전용 search_path 및 연결 단위 임시 테이블만 사용한다. 운영 스키마 전체나
실제 사용자 이력을 검증·변경하지 않는다. SQL에서 JSONB 내부 필드를 추출하므로 DB
내부의 원본 snapshot 읽기·해석 비용은 남아 있다. 요약용 문자열 자체는 SQL에서 자르지
않으며 최종 공개 요약 제한은 기존 서비스 규칙을 따른다.
