# 개별 검색 API — 프론트엔드 확정 계약

기준: develop d14f595. Frontend 구현 완료, Backend 구현·배포 및 실제 E2E 대기.

## Backend 담당 수정 요청

| HTTP API | Agent가 실행할 MCP Tool | source_type |
|---|---|---|
| GET /api/legal/laws | search_laws | law |
| GET /api/legal/consultations | search_consultations | consultation |
| GET /api/legal/cases | search_cases | case |

- 기존 laws/cases 빈 배열 임시 구현을 교체하고 consultations를 추가합니다.
- Backend Agent를 거치되 지정한 유형으로 검색합니다. 허용 Tool과 Runtime 실행 분기도 확인합니다.
- category: housing/labor/consumer. query: trim 후 2~200자. top_k: 기본 3, 1~10.
- 개별 검색은 날짜·증거 부족으로 중단하지 않습니다. 다른 유형 자료로 대체하지 않습니다.
- 세 API 모두 아래 필드를 반환합니다.

```json
{
  "request_id": "search-고유ID",
  "query": "보증금 반환",
  "category": "housing",
  "items": [],
  "total": 0,
  "is_mock": false
}
```

query는 trim한 원래 검색어를 반환합니다. Agent 재작성 검색어는 내부 로그로 관리합니다.
items는 기존 Evidence 배열이며 total은 len(items)입니다. 반환 수는 top_k 이하입니다.
request_id는 빈 문자열이 아니어야 합니다. Frontend는 category/query/건수/source_type/is_mock을 검증합니다.

Evidence 필수: evidence_id, document_id, title, content, source.
source 필수: source_id, title, source_type, url.
ID는 문자열, 날짜는 YYYY-MM-DD 또는 null입니다. summary 및 법령·판례 선택 필드는 기존 Schema를 유지합니다.
출처 URL이 없으면 빈 문자열을 반환합니다. 누락 정보를 생성하지 않습니다.

## 오류

검색 결과 없음은 HTTP 200, items=[], total=0. 오류를 빈 결과로 숨기지 않습니다.

| HTTP | detail.code |
|---|---|
| 422 | VALIDATION_ERROR |
| 502 | MCP_UNAVAILABLE 또는 INVALID_TOOL_RESPONSE |
| 503 | DATABASE_UNAVAILABLE (확인된 DB 장애) |
| 504 | UPSTREAM_TIMEOUT |

오류 본문은 {"detail":{"code":"오류코드","message":"사용자 안내"}} 입니다.
Frontend는 FastAPI 기본 422 목록 응답도 일반 입력 오류 안내로 처리합니다.

## 범위와 검증

- 기존 분석 POST /api/legal/questions 및 FAQ/이력 계약은 이번 개편으로 변경하지 않습니다.
- MCP의 data 배열을 Backend가 items로 변환합니다. Frontend는 MCP/DB 직접 호출을 하지 않습니다.
- API 오류 시 Frontend는 이전 결과를 비우고 오류만 표시합니다. Mock fallback은 없습니다.
- Backend 로그에 request_id, 실행 Tool, category, 반환 건수, 처리 시간과 오류 원인을 기록합니다.
- 배포 후 세 분야 × 세 검색 유형에서 정상/0건/오류, 문서 ID·출처 일치를 확인합니다.
- 현재 로컬 테스트는 대체 응답 기반입니다. 테스트 통과를 실서버 연결 완료로 간주하지 않습니다.
