# 2팀 법률 사례 검색 AI Agent
# Redis 임시 저장 및 PostgreSQL 영구 저장 통합 설계

## 1. 문서 목적

이 문서는 다음 두 가지 요구사항을 하나의 데이터 관리 흐름으로 정리한다.

1. Redis에 사용자의 최근 질문·응답, Agent 실행 상태, Tool Timeline, RAG 검색 결과를 임시 저장한다.
2. 사용자가 **저장하기**를 선택하면 필요한 정보를 PostgreSQL에 영구 저장한다.

핵심 원칙은 다음과 같다.

> Redis는 일정 시간이 지나면 없어져도 되는 실행 중 데이터와 최근 대화 문맥을 관리하고, PostgreSQL은 사용자가 명시적으로 저장한 대화와 답변 근거를 영구 관리한다.

---

## 2. 전체 구조

```text
사용자 질문
    ↓
Redis 최근 대화 문맥 저장
    ↓
Agent 실행
    ├─ 요청 상태 저장
    ├─ Tool Timeline 저장
    └─ RAG 검색 캐시 확인
             ↓
      PostgreSQL + pgvector 검색
             ↓
         LLM 답변 생성
             ↓
Redis에 질문·응답과 완료 상태 저장
             ↓
      사용자 [저장하기]
             ↓
Redis 임시 데이터 조회·검증·정규화
             ↓
PostgreSQL에 대화·검색어·근거 영구 저장
```

Redis 장애나 TTL 만료가 PostgreSQL의 법령·판례 및 RAG 검색 데이터에 영향을 주면 안 된다.

---

## 3. 저장소별 책임

| 저장소 | 저장 내용 | 보존 성격 |
|---|---|---|
| Redis | 최근 질문·응답, 세션 문맥, 현재 요청 상태 | 단기 |
| Redis | Agent 및 MCP Tool Timeline | 단기 |
| Redis | RAG 검색 결과 캐시 | 단기 |
| PostgreSQL | 법령·판례 원문 | 영구 |
| PostgreSQL + pgvector | RAG 청크와 Embedding | 영구, 재생성 가능 |
| PostgreSQL | 사용자가 저장한 질문·답변 | 영구 |
| PostgreSQL | 저장된 답변의 법률 근거와 검색 정보 | 영구 |
| 서버 로그 | 상세 오류, Stack Trace, 운영 로그 | 운영 정책에 따라 관리 |

---

## 4. Redis 저장 설계

### 4.1 최근 질문·응답

```text
Key: legal:session:{session_id}:messages
Type: List
TTL: 마지막 활동 후 30분
제한: 최근 5~10개 메시지
```

사용자 질문 예시:

```json
{
  "message_id": "msg-user-uuid",
  "request_id": "req-uuid",
  "role": "user",
  "category": "labor",
  "content": "퇴사했는데 퇴직금을 받지 못했습니다.",
  "created_at": "2026-09-03T14:00:00+09:00"
}
```

AI 응답 예시:

```json
{
  "message_id": "msg-assistant-uuid",
  "request_id": "req-uuid",
  "role": "assistant",
  "content": "검색된 공식 근거를 바탕으로 정리한 답변",
  "answer_summary": "퇴직금 지급 기한과 관련 근거 안내",
  "document_ids": ["law-labor-001", "case-labor-003"],
  "is_mock": false,
  "created_at": "2026-09-03T14:00:10+09:00"
}
```

권장 필드:

- `message_id`: 메시지 식별
- `request_id`: 대화·검색·Timeline 연결
- `role`: 사용자와 AI 구분
- `category`: 현재 검색 범위
- `content`: 질문 또는 답변
- `answer_summary`: 후속 질문에 사용할 짧은 요약
- `document_ids`: 답변 근거 문서
- `is_mock`: Mock과 실제 데이터 구분
- `created_at`: 메시지 시각과 순서

판례 전체 원문이나 모든 검색 청크는 Redis에 복제하지 않는다. Redis에는 요약과 문서 ID를 저장하고 원문은 PostgreSQL에서 조회한다.

### 4.2 현재 요청 상태

```text
Key: legal:request:{request_id}:status
Type: Hash 또는 JSON String
TTL: 5~10분
```

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

권장 상태:

```text
queued → analyzing → retrieving → generating → completed
                                                └→ failed
```

정확한 진행률을 계산하기 어렵다면 임의의 백분율보다 현재 단계를 표시한다.

### 4.3 Agent 및 Tool Timeline

```text
Key: legal:request:{request_id}:timeline
Type: List
TTL: 30분~1시간
```

MVP에서는 Redis List를 사용한다.

```text
RPUSH  → 이벤트 추가
LRANGE → Timeline 전체 조회
EXPIRE → TTL 설정
```

이벤트 예시:

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

Tool 완료 예시:

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

권장 Timeline 이벤트:

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

사용자 화면에는 이벤트 이름을 이해하기 쉬운 문장으로 변환한다.

```text
질문을 분석하고 있습니다.
이전 대화 문맥을 확인했습니다.
관련 법령과 판례를 검색하고 있습니다.
관련 자료 3건을 찾았습니다.
검색된 근거를 바탕으로 답변을 작성하고 있습니다.
답변이 완료되었습니다.
```

SSE를 고도화하고 새로운 이벤트를 실시간으로 기다려야 할 때 Redis Stream으로 확장할 수 있다. 3일 MVP에서는 Redis List가 충분하다.

### 4.4 RAG 검색 결과 캐시

```text
Key: legal:search:v1:{category}:{query_hash}
Type: JSON String
TTL: 10~30분
```

```json
{
  "query_normalized": "퇴직 후 퇴직금 미지급",
  "category": "labor",
  "keywords": ["퇴직금", "금품청산", "지급기한"],
  "document_types": ["LAW", "CASE"],
  "top_k": 3,
  "document_ids": ["law-labor-001", "case-labor-003"],
  "scores": [0.91, 0.84],
  "retrieval_method": "hybrid",
  "embedding_model": "사용 모델명",
  "cached_at": "2026-09-03T14:00:05+09:00"
}
```

전체 판례 원문보다 문서 ID, 점수, 키워드와 짧은 표시 정보를 저장한다. DB 데이터나 Embedding 모델이 변경되면 `v1`을 `v2`로 바꾸어 이전 캐시를 무효화한다.

---

## 5. 최종 Redis Key 구조

```text
legal:session:{session_id}:messages
# 최근 질문·응답과 후속 질문용 문맥

legal:session:{session_id}:active_request
# 현재 세션에서 처리 중인 request_id

legal:request:{request_id}:status
# 요청의 최신 실행 상태

legal:request:{request_id}:timeline
# Agent와 MCP Tool 실행 이벤트

legal:search:v1:{category}:{query_hash}
# RAG 검색 결과 캐시
```

---

## 6. 사용자의 저장 요청

### 6.1 저장 원칙

사용자가 저장하기를 누르면 Redis 데이터 전체를 그대로 복제하지 않는다. 필요한 데이터만 검증·정규화하여 PostgreSQL에 저장한다.

```text
사용자 [저장하기]
    ↓
Backend가 session_id와 request_id 검증
    ↓
Redis에서 질문·응답·검색 결과·Timeline 조회
    ↓
저장 가능한 완료 상태인지 확인
    ↓
개인정보 최소화 및 필수 필드 검증
    ↓
PostgreSQL Transaction 시작
    ↓
대화 → 메시지 → 검색 기록 → 답변 근거 저장
    ↓
Commit
    ↓
saved_conversation_id 반환
```

PostgreSQL 저장이 성공해도 Redis 데이터를 즉시 삭제할 필요는 없다. 기존 TTL에 따라 최근 문맥으로 계속 사용할 수 있다.

### 6.2 저장하기 API 예시

```http
POST /api/conversations/save
```

```json
{
  "session_id": "demo-session-001",
  "request_id": "req-uuid",
  "title": "퇴직금 미지급 관련 문의"
}
```

응답:

```json
{
  "success": true,
  "conversation_id": "conversation-uuid",
  "saved_at": "2026-09-03T14:05:00+09:00"
}
```

같은 `request_id`를 여러 번 저장해 중복 기록이 생기지 않도록 Unique 제약이나 Idempotency 처리가 필요하다.

---

## 7. PostgreSQL 영구 저장 모델

### 7.1 저장된 대화

```sql
CREATE TABLE saved_conversations (
    id UUID PRIMARY KEY,
    user_id UUID,
    source_session_id VARCHAR(100),
    source_request_id UUID NOT NULL UNIQUE,
    category VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    question_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

역할:

- 사용자가 저장한 대화 묶음
- 저장 목록 화면에 표시할 제목과 요약
- 동일 요청의 중복 저장 방지

로그인이 없는 MVP라면 `user_id`는 nullable로 두고 데모 사용자 또는 세션 ID를 활용할 수 있다. 다만 장기 이력을 사용자에게 제공하려면 안정적인 사용자 식별 방식이 필요하다.

### 7.2 저장된 질문과 응답

```sql
CREATE TABLE saved_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL
        REFERENCES saved_conversations(id)
        ON DELETE CASCADE,
    request_id UUID,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (conversation_id, sequence)
);
```

저장 항목:

- 사용자의 자연어 질문
- AI 최종 응답
- 메시지 역할과 순서
- 원래 요청의 `request_id`

### 7.3 답변에 사용된 RAG 근거

```sql
CREATE TABLE saved_message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id UUID NOT NULL
        REFERENCES saved_messages(id)
        ON DELETE CASCADE,
    document_id BIGINT NOT NULL
        REFERENCES legal_documents(id),
    chunk_id BIGINT
        REFERENCES legal_chunks(id),
    rank INTEGER,
    score DOUBLE PRECISION,
    retrieval_method VARCHAR(20),
    source_title_snapshot TEXT,
    source_url_snapshot TEXT,
    effective_date_snapshot DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

`document_id`와 `chunk_id`를 저장하면 어떤 근거로 답변했는지 추적할 수 있다. 법령이 나중에 개정되어도 저장 당시 표시 내용을 보존해야 한다면 제목, 출처 URL, 시행일 등 최소 Snapshot을 함께 저장한다.

### 7.4 RAG 검색 기록

```sql
CREATE TABLE search_logs (
    id UUID PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    conversation_id UUID
        REFERENCES saved_conversations(id)
        ON DELETE SET NULL,
    user_id UUID,
    session_id VARCHAR(100),
    raw_query TEXT,
    normalized_query TEXT NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    category VARCHAR(20) NOT NULL,
    document_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    result_count INTEGER NOT NULL DEFAULT 0,
    retrieval_method VARCHAR(20),
    cache_hit BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER,
    saved_by_user BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

검색 결과별 순위와 점수가 필요하면 분리한다.

```sql
CREATE TABLE search_log_results (
    search_log_id UUID NOT NULL
        REFERENCES search_logs(id)
        ON DELETE CASCADE,
    document_id BIGINT NOT NULL
        REFERENCES legal_documents(id),
    chunk_id BIGINT
        REFERENCES legal_chunks(id),
    rank INTEGER NOT NULL,
    score DOUBLE PRECISION,
    PRIMARY KEY (search_log_id, rank)
);
```

### 7.5 Tool Timeline 영구 저장 — 선택

일반 사용자의 저장 기능에서 Timeline 전체를 영구 저장할 필요는 없다. 다음 정보만 필요하면 선택적으로 저장한다.

- 호출한 Tool 이름
- 실행 순서
- 성공 또는 실패
- 검색 결과 개수
- 실행 시간
- 오류 코드

```sql
CREATE TABLE saved_tool_events (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL
        REFERENCES saved_conversations(id)
        ON DELETE CASCADE,
    request_id UUID,
    sequence INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    tool_name VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    duration_ms INTEGER,
    result_count INTEGER,
    error_code VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL
);
```

3일 MVP에서는 Timeline을 Redis에서만 보여주고 PostgreSQL에는 질문·답변·근거만 저장해도 충분하다.

---

## 8. RAG 검색어와 키워드 관리

### 8.1 저장할 만한 정보

```text
원본 질문
정규화된 검색어
Agent 또는 검색 Service가 추출한 핵심 키워드
카테고리
검색 문서 유형
검색 결과 개수
검색된 document_id와 chunk_id
검색 순위와 점수
검색 방식
cache hit 여부
검색 시간
```

예시:

```json
{
  "raw_query": "퇴사했는데 퇴직금을 못 받았어요.",
  "normalized_query": "퇴직 후 퇴직금 미지급",
  "keywords": ["퇴직금", "금품청산", "지급기한"],
  "category": "labor",
  "document_types": ["LAW", "CASE"],
  "result_count": 3,
  "retrieval_method": "hybrid",
  "cache_hit": false
}
```

### 8.2 활용 목적

- 카테고리별 인기 법률 질문 분석
- 자주 사용되는 자연어 표현 파악
- 검색 결과가 없는 질문 분석
- 부족한 법령·판례 데이터 수집
- Keyword Search 사전 개선
- FAQ 후보 생성
- RAG 평가 질문 추가

특히 `result_count=0`이거나 검색 점수가 임계값 미만인 질문은 데이터 보강 우선순위를 결정하는 데 유용하다.

### 8.3 저장 정책 선택

#### 정책 A — 사용자가 저장한 검색만 영구 저장

```text
일반 질문 → Redis에만 임시 보관
저장하기 클릭 → 질문·응답·키워드·근거를 PostgreSQL에 저장
```

장점:

- 사용자 의사가 명확하다.
- 개인정보 저장을 최소화한다.
- 3일 MVP에서 구현과 설명이 단순하다.

이번 프로젝트에 가장 권장하는 정책이다.

#### 정책 B — 모든 검색을 익명 통계로 저장

```text
모든 검색
→ 개인정보와 사용자 식별값 제거
→ 정규화된 키워드·카테고리·검색 성공 여부만 저장
```

검색 품질 개선에는 유용하지만 익명화, 보존 기간, 고지 정책이 추가로 필요하다. MVP에서는 후순위로 둔다.

### 8.4 저장하지 않아도 되는 검색 데이터

- 사용자 질문의 Embedding Vector
- LLM의 내부 추론
- 검색 과정의 모든 중간 후보
- 법령·판례 원문의 중복 복사
- 외부 API 원본 응답 전체

질문 Embedding은 필요할 때 다시 생성할 수 있으며 모델이 바뀌면 재사용 가치가 낮다.

---

## 9. Tool Timeline 영구 보존 기준

### Redis에만 저장해도 되는 경우

- 현재 실행 과정을 화면에 표시하는 목적
- 시연용 Timeline
- 단기 오류 확인
- 일정 시간 후 삭제되어도 되는 실행 상태

### PostgreSQL에 저장해야 하는 경우

- 관리자가 과거 실행 기록을 조회해야 함
- 장애 분석을 위해 장기간 보존해야 함
- 어떤 Tool과 근거가 답변에 사용됐는지 감사 추적이 필요함
- 사용자의 승인으로 실제 변경 또는 거래가 실행됨

사용자 승인이 실제 행위에 영향을 주는 경우 다음은 영구 저장해야 한다.

- 승인 주체
- 승인 대상
- 승인 또는 거절 결과
- 승인 시각
- 관련 `request_id`

---

## 10. 보안과 개인정보

Redis와 PostgreSQL 모두 다음 정보를 저장하지 않는다.

- API Key와 비밀번호
- DB 접속 문자열
- 전체 System Prompt
- LLM의 비공개 내부 추론 과정
- 불필요한 주민등록번호, 계좌번호, 전화번호
- HTTP 인증 Header
- 상세 Stack Trace

법률 질문에는 개인정보가 포함될 가능성이 높으므로 다음 원칙을 적용한다.

- 기본 상태에서는 Redis TTL로 단기 보관한다.
- 영구 저장은 사용자 선택을 기준으로 한다.
- 저장 전에 저장 범위와 목적을 사용자에게 안내한다.
- 사용자가 저장한 대화를 삭제할 수 있도록 설계한다.
- 상세 오류는 사용자 데이터와 분리된 서버 로그로 관리한다.

---

## 11. 실패 및 예외 처리

### Redis 장애

```text
Redis 사용 불가
→ 최근 문맥과 캐시 없이 현재 질문만 처리
→ PostgreSQL + pgvector 검색은 계속 수행
```

### 저장하기 시 Redis 데이터 만료

```text
저장 요청
→ Redis Key 없음
→ SESSION_EXPIRED 또는 SAVE_SOURCE_NOT_FOUND 반환
→ 사용자에게 질문을 다시 실행하거나 저장할 수 없음을 안내
```

Frontend가 응답 완료 후 저장 버튼을 보여주는 동안에는 해당 요청의 TTL을 충분히 유지하는 것이 좋다.

### PostgreSQL 저장 실패

```text
Transaction Rollback
→ Redis 임시 데이터는 유지
→ 사용자에게 재시도 안내
→ 동일 request_id 재시도 시 중복 저장 방지
```

---

## 12. 3일 프로젝트 구현 범위

### 반드시 구현

1. Redis에 최근 질문·응답 저장
2. 최근 메시지 5~10개 제한
3. 대화 TTL 30분
4. Redis List 기반 Tool Timeline
5. `request_id`로 질문·응답·Timeline 연결
6. 사용자의 저장하기 API
7. PostgreSQL에 질문·응답 영구 저장
8. 답변에 사용된 `document_id` 연결
9. 동일 `request_id` 중복 저장 방지
10. Redis 장애 시 DB 검색 정상 동작

### 가능하면 구현

1. 정규화된 검색어와 키워드 저장
2. 검색 결과의 순위와 점수 저장
3. `cache_hit`, `latency_ms` 저장
4. 저장된 대화 목록 및 상세 조회
5. Timeline SSE 실시간 표시

### MVP에서 제외 가능

- 모든 검색의 자동 영구 저장
- 질문 Embedding 영구 저장
- Tool Timeline 전체 영구 저장
- Redis Stream과 복잡한 Pub/Sub
- 검색 통계 대시보드
- 정교한 익명화 파이프라인
- 복잡한 법령 버전 Snapshot 시스템

---

## 13. MVP 권장 최소 테이블

일정이 부족하면 다음 세 테이블만 추가한다.

```text
saved_conversations
→ 저장한 대화 묶음과 제목

saved_messages
→ 사용자 질문과 AI 응답

saved_message_sources
→ 답변에 사용된 document_id, chunk_id, 순위, 점수
```

`search_logs`, `search_log_results`, `saved_tool_events`는 시간이 남을 때 추가한다.

---

## 14. 최종 결정 요약

```text
[Redis 임시 저장]
최근 질문·응답
현재 요청 상태
Tool Timeline
RAG 검색 결과 캐시
        ↓
사용자 [저장하기]
        ↓
[PostgreSQL 영구 저장]
저장된 대화
질문과 AI 응답
정규화된 검색어와 핵심 키워드
답변에 사용된 법령·판례 document_id
검색 순위·점수·방식
필요한 최소 Tool 실행 정보
```

가장 적절한 설명은 다음과 같다.

> Redis의 임시 대화와 실행 정보를 사용자의 명시적인 저장 요청에 따라 PostgreSQL의 영구 기록으로 승격한다. 영구 저장 시 Redis를 통째로 복사하지 않고 질문, 응답, 검색어, 키워드 및 법률 근거처럼 재조회와 근거 추적에 필요한 데이터만 정규화하여 저장한다.
