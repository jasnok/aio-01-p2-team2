# 2팀 법률 사례 검색 AI Agent — Redis 설계 요약

## 1. 검토 질문

Redis에 사용자의 자연어 질문과 AI 응답을 저장하려고 한다. 추가로 어떤 정보가 필요하며, Agent와 MCP Tool의 실행 과정을 보여주는 Tool Timeline도 Redis에 저장하는 것이 적절한지 검토한다.

## 2. 결론

질문과 응답을 Redis에 저장하는 방향은 적절하다. 다만 하나의 데이터로 모두 저장하지 말고 다음 네 가지 목적에 따라 Key를 분리한다.

1. 최근 질문·응답과 후속 질문용 대화 문맥
2. 현재 Agent 요청의 실행 상태
3. Agent 및 MCP Tool Timeline
4. 반복되는 RAG 검색 결과 캐시

> Redis는 최근 대화와 실시간 실행 상태를 위한 임시 저장소로 사용하고, 법령·판례·임베딩 및 영구 질문 이력의 기준 저장소는 PostgreSQL로 유지한다.

## 3. Redis 저장 대상

| 저장 대상 | 목적 | 권장 TTL |
|---|---|---:|
| 최근 질문·응답 | 후속 질문 문맥 유지 | 마지막 활동 후 30분 |
| Agent 요청 상태 | 현재 처리 단계 조회 | 5~10분 |
| Tool Timeline | SSE 진행 과정 표시와 임시 디버깅 | 30분~1시간 |
| RAG 검색 결과 | 동일 검색의 응답 시간 단축 | 10~30분 |

Redis가 비워지거나 장애가 발생해도 PostgreSQL 기반 법률 검색은 정상적으로 동작해야 한다.

## 4. 최근 질문·응답

### Key

```text
legal:session:{session_id}:messages
```

- 자료구조: Redis List
- 저장 범위: 최근 5~10개 메시지
- TTL: 마지막 활동 후 30분
- 메시지가 추가될 때 TTL을 갱신하는 Sliding Expiration 방식 권장

### 사용자 질문

```json
{
  "message_id": "msg-uuid",
  "request_id": "req-uuid",
  "role": "user",
  "category": "labor",
  "content": "퇴사했는데 퇴직금을 받지 못했습니다.",
  "created_at": "2026-09-03T14:00:00+09:00"
}
```

### AI 응답

```json
{
  "message_id": "msg-uuid",
  "request_id": "req-uuid",
  "role": "assistant",
  "content": "검색된 공식 근거를 바탕으로 정리한 답변",
  "answer_summary": "퇴직금 지급 기한과 관련 근거 안내",
  "document_ids": ["law-labor-001", "case-labor-003"],
  "is_mock": false,
  "created_at": "2026-09-03T14:00:10+09:00"
}
```

추가 권장 필드:

- `message_id`: 메시지 식별
- `request_id`: 질문·응답·Timeline·검색 결과 연결
- `category`: 검색 범위 유지
- `answer_summary`: 후속 질문용 요약
- `document_ids`: 답변에 사용된 법률 근거
- `is_mock`: Mock과 실제 데이터 구분
- `created_at`: 순서와 시간 확인

판례 전체 원문이나 검색 청크 전체는 Redis 대화 문맥에 복제하지 않는다. 요약과 `document_id`만 저장하고 상세 내용은 PostgreSQL에서 조회한다.

## 5. Agent 요청 상태

### Key

```text
legal:request:{request_id}:status
```

- 자료구조: Redis Hash 또는 JSON String
- TTL: 5~10분

```json
{
  "request_id": "req-uuid",
  "status": "retrieving",
  "current_stage": "search_legal_documents",
  "started_at": "2026-09-03T14:00:00+09:00",
  "updated_at": "2026-09-03T14:00:05+09:00",
  "error_code": null
}
```

권장 상태값:

```text
queued → analyzing → retrieving → generating → completed
                                                └→ failed
```

정확한 진행률을 계산할 수 없다면 임의 백분율 대신 현재 단계를 표시한다.

## 6. Tool Timeline

Tool Timeline을 Redis에 저장하면 다음에 활용할 수 있다.

- Frontend SSE 진행 상태 표시
- Agent가 선택한 Tool 표시
- Tool 실행 시간 확인
- 오류 발생 단계 확인
- Agent·Tool·MCP 구조 시연

### Key

```text
legal:request:{request_id}:timeline
```

### 이벤트 예시

```json
{
  "event_id": "evt-uuid",
  "request_id": "req-uuid",
  "sequence": 3,
  "event": "tool_selected",
  "stage": "retrieval",
  "tool_name": "search_legal_documents",
  "status": "started",
  "message": "관련 법령과 판례를 검색합니다.",
  "created_at": "2026-09-03T14:00:03+09:00",
  "duration_ms": null,
  "details": {
    "category": "labor",
    "top_k": 3
  }
}
```

Tool 완료 이벤트에는 다음 값을 추가할 수 있다.

```json
{
  "event": "tool_completed",
  "tool_name": "search_legal_documents",
  "status": "completed",
  "message": "관련 법률 자료 3건을 찾았습니다.",
  "duration_ms": 1850,
  "details": {
    "result_count": 3,
    "retrieval_method": "hybrid",
    "cache_hit": false
  }
}
```

### 권장 이벤트

```text
request_received
question_analyzed
context_loaded
tool_selected
cache_checked
retrieval_started
retrieval_completed
detail_lookup_started
detail_lookup_completed
answer_generating
answer_completed
request_completed
request_failed
```

사용자 화면에서는 내부 이벤트명을 이해하기 쉬운 문장으로 변환한다.

```text
질문을 분석하고 있습니다.
이전 대화 문맥을 확인했습니다.
관련 법령과 판례를 검색하고 있습니다.
관련 자료 3건을 찾았습니다.
검색된 근거를 바탕으로 답변을 작성하고 있습니다.
답변이 완료되었습니다.
```

### Redis List와 Stream

3일 MVP에서는 Redis List가 가장 현실적이다.

```text
RPUSH  → 이벤트 추가
LRANGE → Timeline 조회
EXPIRE → TTL 설정
```

SSE를 본격적으로 구현하고 새 이벤트를 실시간으로 기다려야 한다면 Redis Stream으로 확장할 수 있다.

```text
MVP → Redis List
SSE 고도화 → Redis Stream
```

## 7. RAG 검색 결과 캐시

### Key

```text
legal:search:v1:{category}:{query_hash}
```

- 자료구조: JSON String
- TTL: 10~30분

```json
{
  "query_normalized": "퇴직 후 퇴직금 미지급",
  "category": "labor",
  "document_types": ["LAW", "CASE"],
  "top_k": 3,
  "document_ids": ["law-labor-001", "case-labor-003"],
  "scores": [0.91, 0.84],
  "retrieval_method": "hybrid",
  "embedding_model": "사용 모델명",
  "cached_at": "2026-09-03T14:00:05+09:00"
}
```

전체 판례 원문보다 문서 ID, 점수, 짧은 표시 정보만 캐시한다. DB 데이터나 Embedding 모델이 변경되면 `v1`을 `v2`로 변경해 이전 캐시를 무효화한다.

## 8. 최종 Key 구조

```text
legal:session:{session_id}:messages
# 최근 질문·응답과 후속 질문용 문맥

legal:session:{session_id}:active_request
# 현재 처리 중인 request_id

legal:request:{request_id}:status
# 요청의 최신 실행 상태

legal:request:{request_id}:timeline
# Agent와 MCP Tool 실행 이벤트

legal:search:v1:{category}:{query_hash}
# RAG 검색 결과 캐시
```

## 9. 저장하지 않을 정보

- API Key와 비밀번호
- DB 접속 문자열
- 전체 System Prompt
- LLM의 비공개 내부 추론 과정
- 주민등록번호, 계좌번호 등 불필요한 개인정보
- 판례 전체 원문과 대량 검색 청크
- HTTP 인증 Header
- 상세 Stack Trace

Timeline에는 사용자용 오류 코드와 메시지만 저장하고 상세 예외는 서버 로그로 관리한다.

```json
{
  "event": "request_failed",
  "status": "failed",
  "message": "법률 자료 검색 중 오류가 발생했습니다.",
  "error_code": "DATABASE_ERROR"
}
```

## 10. Redis와 PostgreSQL 책임 구분

| 요구사항 | 저장 위치 |
|---|---|
| 후속 질문용 최근 대화 | Redis |
| 일정 시간 후 삭제 가능한 질문·응답 | Redis |
| Tool Timeline과 현재 상태 | Redis |
| RAG 검색 결과 캐시 | Redis |
| 법령·판례 원문 | PostgreSQL |
| RAG 청크와 Embedding | PostgreSQL + pgvector |
| 사용자가 나중에 다시 볼 질문 이력 | PostgreSQL |
| 답변에 사용된 근거의 장기 추적 | PostgreSQL |
| 중요한 사용자 승인 기록 | PostgreSQL |

사용자 승인이 실제 업무 행위에 영향을 준다면 승인 주체, 승인 시각, 승인 대상은 Redis가 아니라 PostgreSQL에 영구 기록한다. 단순 Tool Timeline을 시연 화면에 잠시 보여주는 목적이라면 TTL이 적용된 Redis로 충분하다.

## 11. 전체 처리 흐름

```text
사용자 질문 접수
    ↓
request_id 생성 및 request_received 기록
    ↓
Redis 최근 대화 문맥 조회
    ↓
Agent가 MCP Tool 선택 및 Timeline 기록
    ↓
Redis 검색 캐시 확인
    ├─ Cache Hit → 캐시 결과 사용
    └─ Cache Miss
           ↓
      PostgreSQL + pgvector 검색
           ↓
      검색 결과 Redis 단기 캐시
    ↓
retrieval_completed 기록
    ↓
LLM 답변 생성
    ↓
answer_completed 기록
    ↓
질문과 응답을 Redis 최근 문맥에 저장
    ↓
대화 TTL 갱신
```

## 12. 3일 프로젝트 구현 우선순위

### 반드시 구현

1. 최근 질문·응답 Redis 저장
2. 최근 메시지 5~10개 제한
3. 마지막 활동 기준 TTL 30분
4. `request_id`로 질문·응답·Timeline 연결
5. Redis List 기반 Tool Timeline
6. Redis 장애 시 현재 질문만으로 계속 실행
7. 개인정보와 비밀값 저장 금지

### 시간이 남으면 구현

1. RAG 검색 결과 캐시
2. Timeline SSE 실시간 표시
3. Redis Stream 적용
4. Tool 실행 시간 기록
5. 캐시 적중 여부 표시

### MVP에서 제외 가능

- 영구 질문 이력
- 관리자용 과거 실행 이력
- 복잡한 Redis Pub/Sub
- Timeline 통계 대시보드
- 사용자별 장기 검색 기록
- 정교한 유사 질문 캐싱

## 13. 최종 요약

Redis에는 다음 세 묶음을 저장하는 것이 적절하다.

```text
1. 최근 대화
   → 질문, 응답 요약, 카테고리, 근거 document_id

2. 요청 실행 정보
   → request_id, 최신 상태, Tool Timeline, 오류 코드

3. 검색 캐시
   → query hash, category, 검색된 document_id와 점수
```

이를 통해 Redis를 후속 질문 문맥 유지, Agent 실행 과정 시각화, 반복 검색 성능 개선에 실제로 활용할 수 있다. 장기 보존이 필요한 질문 이력과 법률 근거는 PostgreSQL에 저장한다.
