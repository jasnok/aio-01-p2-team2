# LawPath Frontend–Backend API 명세서

> 버전: 확정 v1.2
>
> 최초 작성일: 2026-09-05 / v1.2 확정일: 2026-09-07
>
> 적용 기준: 이 문서의 경로·필드·상태·오류 형식을 Frontend–Backend 구현 계약으로 사용한다.
>
> 현재 구현: Health, 인증, FAQ, 사용자 질문·댓글, 질의 이력, 알림, 관리자, Agent Run API
> 전체 E2E 대기: 실제 MCP 법률 Tool 실행, Redis Session·진행 상태

## 1. 문서 목적

이 문서는 Frontend와 Backend가 독립적으로 개발해도 요청·응답 형식이 달라지지 않도록 공통 HTTP 계약을 정의한다.

```text
Frontend → Backend → Agent → Legal MCP → PostgreSQL
```

Frontend는 업무 기능을 위해 MCP·PostgreSQL·Redis에 직접 접근하지 않는다. 인증, 권한, 소유권, 데이터 저장과 만료 판단은 Backend가 담당한다.

## 2. 상태 표시

| 표시 | 의미 |
|---|---|
| `구현` | 현재 Backend 코드와 테스트에 존재 |
| `골격` | Endpoint 또는 Mock 경로만 있고 실제 의존성 미연동 |
| `확정` | 다음 Backend 구현에서 따라야 하는 계약 |
| `후속` | MVP 연동 뒤 구현하지만 형식은 미리 확정한 계약 |

Backend 담당자는 이 문서를 새로 설계하는 것이 아니라 현재 코드로 구현 가능한지 확인한다. 구현이 불가능하거나 보안상 문제가 있는 부분만 GitHub Issue에 근거와 대안을 남긴다.

## 3. 기본 규칙

### 3.1 주소와 형식

```text
개발 Base URL: http://192.100.200.195:8000
Content-Type: application/json; charset=utf-8
시간: ISO 8601 + timezone, 예) 2026-09-05T20:10:00+09:00
ID: 외부 노출 ID는 UUID 문자열 권장
```

### 3.2 공통 코드값

```text
category: housing | labor | consumer
role: GUEST | USER | ADMIN
question_status: PENDING | ANSWERED
visibility: PUBLIC | PRIVATE
agent_status: completed | failed | stopped
```

`답변 실패`는 게시판 상태로 사용하지 않는다. 시스템 오류는 게시글 상태가 아니라 HTTP 오류와 `error.code`로 표현한다.

### 3.3 인증 확정안

- Backend가 예측 불가능한 불투명 Session Token을 발급하고 Redis에서 사용자·역할·만료를 관리한다.
- Streamlit은 로그인 응답의 Token을 `st.session_state`에만 보관하고 Backend 호출 시 `Authorization: Bearer <token>`으로 전달한다.
- JWT와 브라우저 Local Storage는 현재 Streamlit 구조에서 사용하지 않는다.
- Frontend는 비밀번호나 Session Token을 파일·Local Storage·로그에 저장하지 않는다.
- 비회원은 Streamlit Session별 `guest_id`로 식별하고 Backend가 소유권과 만료를 검증한다.
- 실제 권한은 화면이 아니라 Backend에서 다시 검증한다.

향후 Frontend를 React 등 브라우저 중심 구조로 바꾸면 BFF와 HttpOnly Cookie 방식으로 전환할 수 있다. 이번 Streamlit MVP에서는 위 Bearer Session 방식을 사용한다.

### 3.4 인증 Header

회원 요청:

```http
Authorization: Bearer <opaque-session-token>
```

비회원 소유 데이터 요청:

```http
X-Guest-Id: <guest-uuid>
```

사례 분석처럼 중복 실행을 막아야 하는 생성 요청:

```http
Idempotency-Key: <uuid>
```

같은 사용자·같은 Endpoint·같은 `Idempotency-Key` 요청은 최초 결과를 반환하고 작업을 다시 실행하지 않는다. 키는 최소 24시간 유지한다.

### 3.5 페이지네이션

목록 요청:

```text
page: 1 이상, 기본 1
page_size: 기본 10, 최대 50
```

목록 응답:

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 23,
    "total_pages": 3,
    "has_previous": false,
    "has_next": true
  }
}
```

## 4. 공통 오류 응답

FastAPI 기본 문자열 오류 대신 가능한 한 다음 Envelope를 사용한다.

```json
{
  "detail": {
    "code": "INVALID_REQUEST",
    "message": "입력 내용을 확인해 주세요.",
    "request_id": "req-uuid",
    "field_errors": [
      {"field": "question", "reason": "5자 이상 입력해야 합니다."}
    ]
  }
}
```

| HTTP | code | 의미 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 일반 입력 오류 |
| 401 | `AUTH_REQUIRED` | 로그인 필요 |
| 401 | `AUTH_SESSION_EXPIRED` | 로그인 Session 만료, 다시 로그인 필요 |
| 403 | `FORBIDDEN` | 역할 또는 소유권 부족 |
| 404 | `NOT_FOUND` | 대상 없음 |
| 409 | `CONFLICT` | 중복 또는 현재 상태와 충돌 |
| 422 | `VALIDATION_ERROR` | Schema 검증 실패 |
| 429 | `RATE_LIMITED` | 요청 제한 초과 |
| 502 | `MCP_UNAVAILABLE` | Backend에서 MCP 연결 실패 |
| 503 | `DATABASE_UNAVAILABLE` | DB 연결 실패 |
| 504 | `UPSTREAM_TIMEOUT` | MCP·LLM 제한시간 초과 |

오류 메시지에 비밀번호, DB URL, API Key, 내부 Trace 또는 개인정보를 넣지 않는다.

## 5. Health API

### 5.1 전체 상태 조회 — `구현/골격`

```http
GET /health
```

인증은 필요하지 않다.

현재 응답 예시:

```json
{
  "status": "ok",
  "dependencies": {
    "mcp": "ok",
    "database": "mock",
    "redis": "disabled"
  }
}
```

실제 연동 목표 응답:

```json
{
  "status": "ok",
  "service": "backend",
  "version": "0.1.0",
  "dependencies": {
    "mcp": "ok",
    "database": "ok",
    "redis": "ok"
  }
}
```

의존성 값은 `ok | degraded | unavailable | disabled | mock` 중 하나로 통일한다. HTTP 200이어도 `mock` 또는 `unavailable`이면 실제 연동 완료가 아니다.

## 6. 법률 질문 API

### 6.1 사례 분석 — `구현`

```http
POST /api/legal/questions
Idempotency-Key: <uuid>
```

실제 연동 모드에서는 `Idempotency-Key`를 필수로 사용한다. 현재 Mock·계약 테스트는 단계적으로 Header 검증을 추가한다.

요청:

```json
{
  "session_id": "web-00000000-0000-0000-0000-000000000001",
  "category": "labor",
  "question": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

검증:

- `session_id`: 1~100자
- `category`: `housing`, `labor`, `consumer`
- `question`: 공백 제거 후 5~2,000자

응답:

```json
{
  "request_id": "req-00000000-0000-0000-0000-000000000001",
  "agent_id": "labor",
  "status": "completed",
  "termination_reason": "model_finished",
  "question_summary": "퇴직 후 퇴직금이 지급되지 않은 상황입니다.",
  "key_issues": ["퇴직 여부", "퇴직금 지급 요건"],
  "answer": "검색된 공식 자료를 바탕으로 정리한 답변입니다.",
  "related_laws": [],
  "similar_cases": [],
  "sources": [],
  "follow_up_questions": ["계속근로기간은 얼마인가요?"],
  "cautions": ["법률 자문이 아닌 정보 제공 목적입니다."],
  "is_mock": true
}
```

실행 Fixture:

- `tests/contract/fixtures/legal_question_request.json`
- `tests/contract/fixtures/legal_question_response.json`

### 6.2 Evidence

`related_laws`, `similar_cases`는 같은 Evidence 구조를 사용한다.

```json
{
  "evidence_id": "evidence-uuid",
  "document_id": "123",
  "title": "근로기준법 제36조",
  "content": "근거 원문 또는 검색된 청크",
  "summary": "사용자 표시용 요약",
  "law_name": "근로기준법",
  "article_number": "제36조",
  "case_number": null,
  "case_name": null,
  "court": null,
  "decided_at": null,
  "judgment_result": null,
  "similar_points": [],
  "score": 0.87,
  "source": {
    "source_id": "source-uuid",
    "title": "국가법령정보센터",
    "source_type": "law",
    "url": "https://example.go.kr/original"
  },
  "metadata": {}
}
```

`score`는 관련도이며 승소 가능성이 아니다. 모든 Evidence에는 공식 출처를 포함한다.

### 6.3 법령 검색 — `확정`

```http
GET /api/legal/laws?category=housing&query=보증금&top_k=3
```

### 6.4 판례 검색 — `확정`

```http
GET /api/legal/cases?category=labor&query=퇴직금&top_k=3
```

공통 검증:

- `query`: 공백 제거 후 2~200자
- `category`: `housing | labor | consumer`
- `top_k`: 기본 3, 최소 1, 최대 10

법령·판례 검색 공통 응답:

```json
{
  "query": "퇴직금",
  "category": "labor",
  "items": [],
  "total": 0
}
```

`items`는 6.2의 Evidence 배열이다. 결과가 없으면 오류나 가짜 자료 대신 HTTP 200과 빈 배열을 반환한다.

### 6.5 쉬운 법률 용어 검색 — `후속`

```http
GET /api/legal/terms?category=labor&query=임금
```

```json
{
  "items": [
    {
      "term": "임금체불",
      "description": "정해진 때에 임금이 지급되지 않은 상태를 말합니다."
    }
  ]
}
```

### 6.6 Agent 진행 상태 SSE — `후속`

핵심 동기 API 연결 이후 다음 Endpoint를 추가한다.

```http
GET /api/legal/runs/{request_id}/events
Accept: text/event-stream
```

Event의 `data`는 다음 JSON을 사용한다.

```json
{
  "request_id": "req-uuid",
  "step": "searching_cases",
  "message": "유사 판례를 검색하고 있습니다.",
  "progress": 60,
  "occurred_at": "2026-09-06T20:10:00+09:00"
}
```

`step`은 `validating | selecting_agent | searching_laws | searching_cases | validating_evidence | generating_answer | completed | failed`로 고정한다. 연결이 끊어지면 Frontend는 최종 결과 조회를 시도할 수 있지만 분석 생성 요청 자체를 자동으로 다시 보내지 않는다.

## 7. 인증·사용자 API — `확정`

### 7.1 현재 사용자

```http
GET /api/auth/me
```

```json
{
  "user": {
    "id": "user-or-guest-uuid",
    "role": "GUEST",
    "display_name": "비회원"
  },
  "authenticated": false,
  "history_policy": "7일 보관"
}
```

### 7.2 회원가입

```http
POST /api/auth/register
```

```json
{
  "email": "user@example.com",
  "password": "사용자 입력 비밀번호",
  "display_name": "사용자"
}
```

비밀번호 원문을 저장하거나 로그에 기록하지 않는다.

### 7.3 로그인·로그아웃

```http
POST /api/auth/login
POST /api/auth/logout
```

로그인 성공 응답:

```json
{
  "session_token": "opaque-random-token",
  "expires_in": 28800,
  "user": {
    "id": "user-uuid",
    "role": "USER",
    "display_name": "사용자"
  }
}
```

기본 로그인 Session은 8시간이며 활동 중 갱신 정책은 Backend 구현 시 문서에 함께 기록한다. 로그아웃은 전달된 Session Token을 Redis에서 즉시 폐기한다.

## 8. 공지 FAQ API — `확정`

### 8.1 공개 FAQ 조회

```http
GET /api/faqs?category=housing
```

비회원 포함 누구나 조회 가능하다. `is_active=true`만 반환하며 `is_pinned DESC, display_order ASC, updated_at DESC`로 정렬한다. 상단 고정 FAQ의 `display_order=0`을 허용한다.

```json
{
  "items": [
    {
      "id": "faq-uuid",
      "category": "housing",
      "question": "계약이 끝나면 보증금은 언제 반환하나요?",
      "answer": "일반적인 확인 사항을 안내합니다.",
      "is_pinned": true,
      "display_order": 1,
      "updated_at": "2026-09-05T20:10:00+09:00"
    }
  ]
}
```

### 8.2 관리자 FAQ 관리

```http
GET    /api/admin/faqs
POST   /api/admin/faqs
PATCH  /api/admin/faqs/{faq_id}
DELETE /api/admin/faqs/{faq_id}
```

`ADMIN`만 실행할 수 있다. 생성·수정 Body:

```json
{
  "category": "housing",
  "question": "질문",
  "answer": "답변",
  "is_active": true,
  "is_pinned": false,
  "display_order": 10
}
```

## 9. 사용자 질문 게시판 API — `확정`

### 9.1 공개 질문 목록

```http
GET /api/questions?page=1&page_size=10&category=housing&status=PENDING&query=보증금
```

정렬 확정안:

```text
1. PENDING 답변 대기
2. ANSWERED 답변 완료
3. 같은 상태에서는 created_at DESC, id DESC
```

응답:

```json
{
  "items": [
    {
      "id": "question-uuid",
      "category": "housing",
      "title": "보증금 반환 질문",
      "status": "PENDING",
      "visibility": "PUBLIC",
      "content_visibility": "PUBLIC",
      "display_name": "비회원",
      "is_owner": true,
      "created_at": "2026-09-05T20:10:00+09:00",
      "updated_at": "2026-09-05T20:10:00+09:00",
      "expires_at": "2026-09-12T20:10:00+09:00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 23,
    "total_pages": 3,
    "has_previous": false,
    "has_next": true
  }
}
```

### 9.2 질문 작성

```http
POST /api/questions
```

비회원·회원 모두 가능하다.

```json
{
  "category": "housing",
  "title": "보증금 질문",
  "content": "보증금 반환에 필요한 자료가 궁금합니다.",
  "post_password": "사용자가 입력한 게시글 비밀번호",
  "visibility": "PUBLIC",
  "privacy_confirmed": true
}
```

검증:

- 제목 2~100자
- 내용 10~2,000자
- 게시글 비밀번호 4~20자
- 개인정보 확인 필수
- 생성 상태는 항상 `PENDING`
- 비회원은 생성 시점부터 7일 후 `expires_at` 설정
- 회원은 기본적으로 만료 없음

### 9.3 질문 상세·잠금 해제·수정·삭제

```http
GET    /api/questions/{question_id}
POST   /api/questions/{question_id}/unlock
PATCH  /api/questions/{question_id}
DELETE /api/questions/{question_id}
```

- 목록에서는 공개글과 비밀글의 제목·분야·상태·작성시각을 누구나 확인할 수 있다.
- `PUBLIC` 상세 내용과 댓글은 누구나 조회할 수 있다.
- `PRIVATE` 상세 내용과 댓글은 작성자 또는 관리자만 조회할 수 있다.
- 비밀글 작성자는 Session 소유권과 게시글 비밀번호를 확인해 잠금을 해제한다. 잠금 해제 상태는 짧은 시간(권장 10분)만 유지한다.
- 목록 검색은 공개글의 제목·본문, 비밀글의 제목만 대상으로 한다.
- 수정·삭제도 작성자 Session과 게시글 비밀번호를 모두 확인한 경우만 허용한다.
- 게시글 비밀번호 원문은 저장하지 않고 Backend에서 안전한 Password Hash로 저장한다.
- Frontend·로그·오류 응답에는 게시글 비밀번호와 Hash를 반환하지 않는다.
- `PENDING` 질문만 원문 수정 가능하다.
- `ANSWERED` 질문은 기존 근거 보존을 위해 직접 수정하지 않는다.
- 관리자는 운영 목적으로 모든 질문을 삭제할 수 있다. 이때 요청 Body의 `reason`은 필수이며 관리자 ID, 질문 ID, 사유, 삭제 시각을 감사 로그에 남긴다.

잠금 해제 요청:

```json
{
  "post_password": "사용자가 입력한 게시글 비밀번호"
}
```

성공하면 Backend가 현재 Session과 질문 ID에 묶인 단기 접근 권한을 발급한다. 비밀번호와 Hash는 응답하지 않는다.

### 9.4 답변 완료 질문 다시 질문

```http
POST /api/questions/{question_id}/resubmit
```

기존 질문을 바꾸지 않고 `PENDING` 상태의 새 질문을 생성하며 `parent_question_id`로 연결한다.

### 9.5 관리자 답변 등록

```http
PATCH /api/admin/questions/{question_id}/answer
```

```json
{
  "answer": "관리자 또는 승인된 답변 내용"
}
```

성공 시 상태를 `ANSWERED`로 변경한다. 답변 생성 실패는 `FAILED` 게시판 상태로 저장하지 않고 요청 오류로 반환한다.

### 9.6 사용자 댓글 조회·작성·수정·삭제

```http
GET    /api/questions/{question_id}/comments?page=1&page_size=20
POST   /api/questions/{question_id}/comments
PATCH  /api/questions/{question_id}/comments/{comment_id}
DELETE /api/questions/{question_id}/comments/{comment_id}
```

작성 요청:

```json
{
  "content": "도움이 되는 댓글 내용입니다.",
  "comment_password": "비회원 댓글 수정·삭제용 비밀번호"
}
```

수정 요청:

```json
{
  "content": "수정한 댓글 내용입니다.",
  "comment_password": "비회원인 경우에만 입력"
}
```

규칙:

- `PUBLIC` 질문은 비회원·회원·관리자 모두 댓글 조회와 작성이 가능하다.
- `PRIVATE` 질문은 작성자와 관리자만 댓글 조회와 작성이 가능하다.
- 댓글은 작성자만 수정·삭제할 수 있고, 관리자는 운영 목적으로 삭제할 수 있다.
- 비회원 댓글은 4~20자의 댓글 비밀번호가 필수이며 원문 대신 안전한 Password Hash만 저장한다.
- 회원 댓글은 로그인 Session 소유권으로 확인하므로 별도 댓글 비밀번호를 받지 않는다.
- 댓글 내용은 2~1,000자이며 기본 정렬은 `created_at ASC, id ASC`로 한다.
- 비회원 댓글은 연결된 비회원 Session 보관기간과 함께 만료한다.
- 댓글 작성 시 질문 작성자에게 `COMMENT_CREATED` 알림을 생성하되, 비밀글 본문이나 댓글 원문은 알림 메시지에 포함하지 않는다.
- 공개 댓글은 공식 법률 답변과 구분하며 관리자 답변 상태(`PENDING`, `ANSWERED`)를 변경하지 않는다.

## 10. 통합 질의 이력 API — `확정`

### 10.1 이력 목록

```http
GET /api/history?page=1&page_size=10&type=all&category=housing
```

`type`: `all | legal_analysis | user_question`

- 비회원은 현재 익명 Session 소유 이력만 조회한다.
- 비회원 이력은 7일 후 삭제한다.
- 회원은 로그인 계정의 이력을 영구 조회한다.
- 다른 사용자의 비공개 이력은 반환하지 않는다.

### 10.2 이력 상세·삭제

```http
GET    /api/history/{history_id}
DELETE /api/history/{history_id}
```

작성자 소유권을 Backend에서 확인한다. 전체 삭제가 필요하면 명시적인 별도 Endpoint와 재확인 UI를 사용한다.

## 11. CORS·Timeout 확정안

```text
허용 Origin: http://192.100.200.232:8501
Frontend → Backend: 30초
Backend → MCP: 10초
MCP → DB: 5초
```

- 허용 Origin은 정확히 지정하고 운영 환경에서 `*`를 사용하지 않는다.
- Timeout을 Mock 성공으로 바꾸지 않는다.
- 실패한 구간을 공통 오류 코드로 Frontend에 전달한다.
- 읽기 요청만 제한적으로 재시도하고 생성·수정·삭제는 자동 재시도하지 않는다.

## 12. 권한표

| 기능 | 비회원 | 회원 | 관리자 |
|---|:---:|:---:|:---:|
| 공개 FAQ·질문 조회 | 가능 | 가능 | 가능 |
| 질문 작성 | 가능 | 가능 | 가능 |
| 본인 질문 수정·삭제 | 가능 | 가능 | 가능 |
| 공개글 내용·댓글 조회 | 가능 | 가능 | 가능 |
| 공개글 댓글 작성 | 가능 | 가능 | 가능 |
| 비밀글 내용·댓글 조회 | 본인만 | 본인만 | 가능 |
| 비밀글 댓글 작성 | 본인만 | 본인만 | 가능 |
| 본인 댓글 수정·삭제 | 비밀번호 확인 | Session 확인 | 가능 |
| 이력 보관 | 7일 | 영구 | 계정 정책 |
| 공지 FAQ 관리 | 불가 | 불가 | 가능 |
| 사용자 질문 답변 | 불가 | 불가 | 가능 |

관리자의 비밀글 열람과 댓글 삭제는 운영·신고 대응 목적에 한하며 감사 로그를 남긴다.

## 13. 계약 변경 규칙

응답 필드를 변경할 때 다음 항목을 한 PR에서 함께 갱신한다.

```text
backend/app/schemas
frontend/core/models.py
frontend/clients/backend_client.py
tests/contract/fixtures
tests/contract
docs/architecture/API 명세서.md
```

Breaking Change는 필드 삭제, 타입 변경, Enum 변경, 의미 변경을 포함한다. 팀 승인 없이 공통 계약을 단독 변경하지 않는다.

## 14. 구현 확정 사항

다음 항목은 구현 기본값으로 확정한다. Backend 담당자는 기술적으로 구현 불가능하거나 보안상 문제가 있는 항목만 GitHub Issue에 의견을 남긴다.

1. 인증은 `Opaque Bearer Session Token + Redis Session`을 사용한다.
2. Frontend는 Backend만 호출한다.
3. 질문 상태는 `PENDING`, `ANSWERED`만 사용한다.
4. 질문 목록은 답변 대기 우선, 상태별 최신순으로 정렬한다.
5. 페이지 크기는 기본 10, 최대 50으로 제한한다.
6. 비회원 질문·이력은 7일, 회원 이력은 영구 보관한다.
7. 답변 완료 질문 수정은 새 질문 생성으로 처리한다.
8. 공통 오류 Envelope와 위 HTTP 상태 코드를 사용한다.
9. 실제 권한과 소유권은 Backend에서 검증한다.
10. Health 응답에서 Mock과 실제 연결 상태를 명확히 구분한다.
11. 질문은 `PUBLIC`과 `PRIVATE`을 지원하며 생성 화면의 기본값은 `PRIVATE`이다.
12. 공개글은 전체 공개, 비밀글은 작성자와 관리자만 상세·댓글에 접근한다.
13. 비회원 댓글 비밀번호는 Hash로 저장하고 회원 댓글은 Session 소유권으로 확인한다.

## 15. 알림 API — `후속`

Frontend는 Redis나 PostgreSQL을 직접 조회하지 않고 Backend 알림 API만 호출한다.

알림 기본 형식:

```json
{
  "id": "notification-uuid",
  "type": "QUESTION_ANSWERED",
  "title": "질문에 답변이 등록되었습니다.",
  "message": "작성한 질문의 답변을 확인해 주세요.",
  "severity": "success",
  "target_type": "question",
  "target_id": "question-uuid",
  "category": "housing",
  "created_at": "2026-09-06T17:30:00+09:00",
  "is_read": false
}
```

권장 API:

```http
GET    /api/notifications?page=1&page_size=20
GET    /api/notifications/unread-count
PATCH  /api/notifications/{notification_id}/read
PATCH  /api/notifications/read-all
DELETE /api/notifications/{notification_id}
DELETE /api/notifications/read-items
```

규칙:

- 비회원 알림은 비회원 Session 소유자에게만 반환한다.
- 회원 알림과 읽음 상태는 PostgreSQL에 영속 저장한다.
- Redis는 읽지 않은 개수와 최근 알림 Cache에만 사용한다.
- Agent 진행 중 상태는 SSE로 전달하고 완료·실패 결과만 알림으로 남긴다.
- 알림 목록은 읽지 않은 알림 우선, 같은 상태에서는 최신순으로 정렬한다.
- 비밀번호, API Key, 내부 오류 전체 내용은 알림에 포함하지 않는다.
- 알림 대상에 접근 권한이 없으면 관련 화면을 열지 않는다.
- `read-items`는 동적 경로 `/{notification_id}`와 충돌하지 않도록 읽은 알림 일괄 삭제에 사용한다.

## 16. Agent 실행 상태 API — polling 우선

```http
POST /api/agent-runs
GET  /api/agent-runs/{run_id}
POST /api/agent-runs/{run_id}/cancel
GET  /api/agent-runs/{run_id}/events
```

- `POST` 요청에는 `Idempotency-Key` Header가 필수다. 같은 사용자·같은 Key는 같은 `run_id`와 현재 상태를 반환한다.
- 상태는 `QUEUED | RUNNING | WAITING_APPROVAL | COMPLETED | FAILED | CANCELLED`다.
- 첫 연동에서는 `GET /api/agent-runs/{run_id}` polling을 사용한다.
- `/events`는 현재 polling 호환 JSON 이벤트 목록이며, SSE는 polling 안정화 후 같은 경로로 확장한다.
- Mock 단계의 실행 상태는 메모리에 저장되고 Backend 재시작 시 초기화된다.

## 17. Backend 구현 기준과 순서

Backend는 아래 구조로 책임을 나눈다.

```text
router: HTTP 입력·출력과 상태 코드
schema: 이 문서의 요청·응답 검증
service: 인증·소유권·업무 규칙과 Agent 실행
repository: PostgreSQL CRUD
mcp_client: Legal MCP 호출
session_store: Redis Session·Idempotency·진행 상태
```

구현 순서:

1. 기존 `/health`, `/api/legal/questions` 응답을 명세와 계약 테스트로 고정한다.
2. 공통 오류 Envelope와 `request_id`를 적용한다.
3. `Idempotency-Key` 중복 방지를 적용한다.
4. 인증과 역할 검증을 구현한다.
5. 공지 FAQ와 사용자 질문 CRUD를 구현한다.
6. 통합 질의 이력과 알림을 구현한다.
7. Redis 진행 상태와 SSE는 핵심 동기 API 연결 후 별도 PR로 추가한다.

각 Endpoint 완료 기준:

- FastAPI Schema와 OpenAPI 문서가 이 명세와 일치한다.
- 정상·입력 오류·인증·소유권·의존성 장애 테스트가 있다.
- 비밀번호, Session Token, 내부 예외 내용이 로그와 응답에 노출되지 않는다.
- Frontend와 공통 Fixture를 이용한 계약 테스트가 통과한다.
