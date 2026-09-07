# LawPath Frontend–Backend API 명세서

> 버전: 초안 v1.0
>
> 작성일: 2026-09-05
>
> 현재 구현: Health, 법률 질문 API
>
> 추천·팀 승인 필요: 인증, FAQ, 사용자 질문, 질의 이력, 관리자 API

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
| `추천` | Frontend Mock 기준으로 제안한 계약, 팀 승인 후 구현 |

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

### 3.3 인증 추천안

- Backend가 HttpOnly·Secure·SameSite Cookie 기반 Session을 발급한다.
- Redis는 Session 상태와 만료를 관리한다.
- Frontend는 비밀번호나 인증 Token을 Local Storage에 저장하지 않는다.
- 비회원도 Backend가 발급한 익명 Session Cookie로 본인 질문을 식별한다.
- Frontend 요청은 Cookie 전달을 위해 credentials를 포함한다.
- 실제 권한은 화면이 아니라 Backend에서 다시 검증한다.

팀 동의 요청: JWT를 브라우저 저장소에 보관하지 않고 `HttpOnly Cookie + Redis Session`을 기본 인증 방식으로 확정할지 확인한다.

### 3.4 페이지네이션

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

추천 운영 응답:

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
```

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

## 7. 인증·사용자 API — `추천`

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

로그인 성공 시 응답 Body보다 `Set-Cookie`로 Session을 발급하는 방식을 추천한다.

## 8. 공지 FAQ API — `추천`

### 8.1 공개 FAQ 조회

```http
GET /api/faqs?category=housing
```

비회원 포함 누구나 조회 가능하다. `is_active=true`만 반환하며 `is_pinned DESC, display_order ASC`로 정렬한다.

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

## 9. 사용자 질문 게시판 API — `추천`

### 9.1 공개 질문 목록

```http
GET /api/questions?page=1&page_size=10&category=housing&status=PENDING&query=보증금
```

정렬 추천안:

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
      "content": "개인정보가 제거된 공개 질문 내용입니다.",
      "status": "PENDING",
      "answer": null,
      "visibility": "PUBLIC",
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
  "visibility": "PUBLIC",
  "privacy_confirmed": true
}
```

검증:

- 제목 2~100자
- 내용 10~2,000자
- 개인정보 확인 필수
- 생성 상태는 항상 `PENDING`
- 비회원은 생성 시점부터 7일 후 `expires_at` 설정
- 회원은 기본적으로 만료 없음

### 9.3 질문 상세·수정·삭제

```http
GET    /api/questions/{question_id}
PATCH  /api/questions/{question_id}
DELETE /api/questions/{question_id}
```

- 공개 질문은 누구나 조회 가능하다.
- 비공개 질문은 작성자만 조회 가능하다.
- 수정·삭제는 작성자 또는 정책상 허용된 관리자만 가능하다.
- `PENDING` 질문만 원문 수정 가능하다.
- `ANSWERED` 질문은 기존 근거 보존을 위해 직접 수정하지 않는다.

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

## 10. 통합 질의 이력 API — `추천`

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

## 11. CORS·Timeout 추천안

```text
허용 Origin: http://192.100.200.232:8501
Frontend → Backend: 30초
Backend → MCP: 10초
MCP → DB: 5초
```

- Cookie 인증을 위해 정확한 Origin만 허용하고 `*`와 credentials를 함께 사용하지 않는다.
- Timeout을 Mock 성공으로 바꾸지 않는다.
- 실패한 구간을 공통 오류 코드로 Frontend에 전달한다.
- 읽기 요청만 제한적으로 재시도하고 생성·수정·삭제는 자동 재시도하지 않는다.

## 12. 권한표

| 기능 | 비회원 | 회원 | 관리자 |
|---|:---:|:---:|:---:|
| 공개 FAQ·질문 조회 | 가능 | 가능 | 가능 |
| 질문 작성 | 가능 | 가능 | 가능 |
| 본인 질문 수정·삭제 | 가능 | 가능 | 가능 |
| 비공개 질문 조회 | 본인만 | 본인만 | 정책에 따라 제한 |
| 이력 보관 | 7일 | 영구 | 계정 정책 |
| 공지 FAQ 관리 | 불가 | 불가 | 가능 |
| 사용자 질문 답변 | 불가 | 불가 | 가능 |

관리자도 개인정보가 포함된 사용자 원문을 무조건 열람할 수 있게 하지 않고, 운영 목적과 감사 로그 정책을 별도로 확정한다.

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

## 14. 팀 동의 요청 항목

다음 추천안을 기본값으로 제안한다. 이견이 없다면 Fixture와 Backend Schema에 반영한다.

팀원별 확인 결과와 최종 확정 상태는 `docs/팀 합의 요청사항.md`에서 관리한다.

1. 인증은 `HttpOnly Cookie + Redis Session`을 사용한다.
2. Frontend는 Backend만 호출한다.
3. 질문 상태는 `PENDING`, `ANSWERED`만 사용한다.
4. 질문 목록은 답변 대기 우선, 상태별 최신순으로 정렬한다.
5. 페이지 크기는 기본 10, 최대 50으로 제한한다.
6. 비회원 질문·이력은 7일, 회원 이력은 영구 보관한다.
7. 답변 완료 질문 수정은 새 질문 생성으로 처리한다.
8. 공통 오류 Envelope와 위 HTTP 상태 코드를 사용한다.
9. 실제 권한과 소유권은 Backend에서 검증한다.
10. Health 응답에서 Mock과 실제 연결 상태를 명확히 구분한다.
