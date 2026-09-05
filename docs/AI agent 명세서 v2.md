# 생활 법률 검색 AI Agent 아키텍처 설계서 v2

> 버전: v2.0  
> 작성일: 2026-09-05  
> 기준: `docs/AI agent 명세서.md`  
> 범위: Frontend·Backend·Legal MCP·DB·Redis·Supabase 전체 프로젝트

## 1. v1에서 변경된 점

| 항목 | v1 | v2 |
|---|---|---|
| 서버 | 계층 중심 설명 | 담당자 4대 PC 분산 실행 |
| Primary DB | PostgreSQL + pgvector | DB PC의 Docker PostgreSQL |
| Supabase | 미확정 | 백업·외부 통합·수동 Fallback |
| 사용자 | 익명 중심 | `GUEST`, `USER`, `ADMIN` |
| 인증 | 로그인 미확정 | Backend + Redis Session 권장 |
| 이력 | 명시적 저장 | 비회원 7일, 회원 동의 후 영구 |
| FAQ | 고정 조회 | 공지형 FAQ + 개인 질문 CRUD |
| Redis | 문맥·상태·Cache | DB PC 운영, Backend/MCP가 분리 사용 |
| CRUD | 상세 경계 없음 | 사용자 CRUD는 Backend, Legal MCP는 읽기 전용 |
| 장애 | 일반 오류 | Redis 저하 운영과 Supabase 수동 Fallback |

v1은 보존한다. 신규 정책은 팀 승인 후 Team Contract v2로 확정한다. Frontend의 현재 Mock 구현은 `docs/프론트엔드 진행상황 공유.md`에서 별도 관리한다.

## 2. 프로젝트 목적

사용자가 생활 법률 상황을 입력하면 전문 Agent가 공식 법령과 유사 판례를 검색하고 출처와 함께 정리한다.

```text
housing  → HousingAgent
labor    → LaborAgent
consumer → ConsumerAgent
```

법률 자문, 범죄 성립 단정 또는 승패 예측은 제공하지 않는다.

## 3. 전체 시스템 구조

```text
Frontend PC: Streamlit
  ↓ HTTP
Backend PC: FastAPI + AgentRuntime + Auth/CRUD
  ├─ 법률 검색 → MCP PC
  └─ 사용자·FAQ·이력 → DB PC

MCP PC: Legal MCP Server
  ↓
DB PC: Docker PostgreSQL + pgvector + Redis + Ingestion

Supabase PostgreSQL: 백업·외부 통합·수동 Fallback
```

원칙:

- Frontend는 Backend만 호출한다.
- Backend의 법률 검색은 Legal MCP를 통한다.
- Backend는 사용자·FAQ·이력만 DB에 직접 CRUD한다.
- MCP는 법률 문서·Chunk만 접근한다.
- Frontend는 DB·Redis·MCP에 직접 접근하지 않는다.
- Docker와 Supabase에 한 요청을 동시에 쓰지 않는다.

## 4. 파트별 책임

| 파트 | 책임 |
|---|---|
| Frontend | Streamlit, 입력·결과, 역할별 UX, Backend Client |
| Backend | API, AgentRuntime, 인증, 소유권, FAQ·이력 CRUD |
| MCP | Legal Tool, Hybrid Search, Repository, 검색 Cache |
| DB | Docker PostgreSQL·Redis, Migration, 수집·Embedding |
| Supabase | 백업·외부 통합·수동 Fallback |

Redis 인프라는 DB 담당이 운영하고 Backend와 MCP 담당이 각 Key 사용 코드를 구현한다.

## 5. Agent 설계

```text
AgentProfile → AgentRegistry → AgentRuntime
```

- category별 전문 Agent 하나를 선택한다.
- Tool Allowlist는 Backend 코드에서 검증한다.
- 최대 4 Step, 최대 3 Tool Call을 권장한다.
- MCP 10초, LLM 20초 Timeout을 초기값으로 사용한다.
- 동일 Tool과 동일 arguments의 반복 호출을 차단한다.
- ToolResult 이후 다음 Tool 또는 최종 답변을 재판단한다.
- Evidence가 없으면 추측하지 않고 `no_evidence`로 종료한다.

## 6. Legal MCP Tool

```text
search_laws(query, category, top_k=3)
search_cases(query, category, top_k=3)
get_law_article(law_name, article_number)
```

모든 Tool은 읽기 전용이다.

```text
결과 있음 → success=true, data=[Evidence]
결과 없음 → success=true, data=[] 또는 null
실행 실패 → success=false, error_code 지정
```

회원·FAQ·질의 CRUD를 Legal MCP Tool에 추가하지 않는다.

## 7. 핵심 응답 계약

```text
request_id, agent_id, status, termination_reason
question_summary, key_issues, answer
related_laws, similar_cases, sources
follow_up_questions, cautions, is_mock
```

관련도는 검색 유사도이며 승소 가능성이 아니다. Source에 없는 법령·판례·사건번호·URL을 생성하지 않는다.

## 8. 역할과 권한

| 기능 | `GUEST` | `USER` | `ADMIN` |
|---|---|---|---|
| 법률정보·FAQ 조회 | 가능 | 가능 | 가능 |
| 사례 분석·검색 | 가능 | 가능 | 가능 |
| 개인 질문 | 본인, 7일 | 본인, 영구 | 본인 가능 |
| 여러 기기 이력 | 불가 | 가능 | 가능 |
| 공지 FAQ 관리 | 불가 | 불가 | 가능 |
| 운영정보 | 불가 | 불가 | 가능 |
| 공개된 사용자 질문 조회 | 가능 | 가능 | 가능 |
| 비공개·삭제된 타인 질문 | 불가 | 불가 | 운영상 필요한 경우만 Audit 후 접근 |

개인 질문은 기본 비공개다. 권한과 소유권은 Backend에서 검증한다.

## 9. 인증 권장안

```text
회원 로그인
→ Backend가 임의 Session ID 발급
→ HttpOnly Cookie
→ Redis에서 user_id·role 확인
```

비회원은 서명된 `guest_token` Cookie로 식별한다. 비밀번호 원문, 질문과 인증 Token을 Local Storage에 저장하지 않는다.

## 10. FAQ, 사용자 질문 게시판과 통합 질의 이력

```text
FAQ
├─ 공지형 자주 하는 질문: 누구나 조회, 관리자 CRUD
└─ 사용자 질문 게시판
   ├─ 공개 동의한 질문을 최신순으로 조회
   ├─ 누구나 질문 작성
   └─ 작성자만 수정·삭제

conversation_type
├─ CASE_ANALYSIS
└─ FAQ_QUESTION
```

- 비회원 질문은 작성일 기준 7일 보관한다.
- 회원 질문은 안내와 동의 후 영구보관한다.
- 공개 질문만 사용자 질문 게시판에 표시한다.
- 목록에는 닉네임 또는 `비회원`, category, 제목, 내용 요약, 답변 상태와 작성일을 표시한다.
- 이름·연락처·주소·계좌번호 등 개인정보는 입력 경고와 마스킹 정책을 적용한다.
- 답변 전 질문은 수정 가능하다.
- 답변 완료 후에는 원문을 덮어쓰지 않고 새 질문으로 재분석한다.

게시판 조회 API는 서버 기준 페이지네이션을 사용한다.

```text
GET /api/questions?visibility=PUBLIC&page=1&page_size=10&sort=created_at_desc

items, page, page_size, total_items, total_pages, has_next, has_previous
```

`page_size` 기본값은 10, 최대값은 50으로 제한한다. 최신순 정렬은 `created_at DESC, id DESC`로 고정해 같은 시각의 글도 안정적으로 정렬한다.

## 11. 데이터 구조

```text
users
faq_articles
saved_conversations
saved_messages
saved_message_sources
legal_documents
legal_chunks
ingestion_runs
audit_logs
```

회원 질문은 `user_id`만, 비회원 질문은 `guest_id + expires_at`을 갖도록 Check Constraint를 둔다.

## 12. Docker PostgreSQL과 Supabase

- DB PC의 Docker PostgreSQL이 Primary다.
- 앱의 읽기·쓰기는 Primary 한 곳에만 수행한다.
- Supabase는 Snapshot 백업, 외부 통합과 수동 Fallback에 사용한다.
- 초기 Fallback은 법령·판례·공지 FAQ 읽기 중심이다.
- 개인정보의 Supabase 복제는 정책 승인 후 진행한다.
- Migration은 하나의 원본을 두 DB에 동일하게 적용한다.

## 13. Redis

```text
backend:auth:session:{id}
backend:guest:session:{id}
backend:agent:run:{request_id}
backend:conversation:context:{session_id}
backend:cache:faq:{category}
mcp:cache:law:{query_hash}
mcp:cache:case:{query_hash}
```

Redis는 영구 원본이 아니다. Redis 장애 시 Cache와 최근 문맥 없이 핵심 PostgreSQL 검색을 유지한다.

## 14. 안전·오류 정책

| 상황 | 상태 |
|---|---|
| 정상 완료 | `completed + model_finished` |
| 근거 없음 | `completed + no_evidence` |
| 잘못된 입력 | `INVALID_REQUEST` |
| 미지원 분야 | `UNSUPPORTED_CATEGORY` |
| Tool 위반 | `failed + invalid_tool_call` |
| MCP 실패 | `failed + mcp_tool_error` |
| Model 실패 | `failed + model_error` |
| 실행 제한 | `stopped + max_steps_exceeded` |

모든 답변에 정보 제공 목적과 전문가 상담 안내를 포함한다. Trace는 실행 사실만 기록하며 내부 추론·비밀정보를 저장하지 않는다.

## 15. 전체 테스트 기준

- 올바른 Agent 선택과 Tool Allowlist
- ToolResult 이후 재판단
- Evidence 기반 답변과 no-evidence
- 최대 Step·Tool 횟수
- MCP·Model·DB·Redis 오류 구분
- 회원·비회원 소유권
- 관리자 FAQ 권한
- 비회원 7일 만료
- Redis 장애 중 핵심 검색
- Docker/Supabase 동시 쓰기 금지
- 대표 질문 3개 네 PC E2E

## 16. 팀 합의가 필요한 항목

1. 각 PC의 실제 IP·Port와 방화벽
2. Frontend–Backend API JSON
3. Backend–MCP Transport·ToolResult·Timeout
4. Migration 원본과 DB 계정
5. Redis Session·Cookie·TTL
6. 비회원 보관 동의 문구
7. 관리자 열람 범위와 Audit
8. Supabase 백업 범위·주기
9. Fallback 전환·복구 담당

## 17. 구현 순서

```text
1. Team Contract v2 승인
2. DB PC PostgreSQL·Redis
3. MCP search_cases
4. Backend LaborAgent 첫 Loop
5. Frontend 실제 연결
6. Housing·Consumer 확장
7. 인증·FAQ·질의 이력
8. 검색 평가·안전성 테스트
9. Supabase 백업·Fallback
10. 네 PC E2E·장애 테스트
```

첫 통합 목표:

```text
퇴직금 질문 → LaborAgent → search_cases → pgvector
→ 공식 판례 Top 3 → Frontend 표시
```

## 18. 결론

```text
전체 프로젝트
= 4대 PC 분산 서버
+ 공통 AgentRuntime
+ 읽기 전용 Legal MCP
+ Docker PostgreSQL Primary
+ Redis 임시 상태·Cache
+ Backend 역할·소유권 CRUD
+ Supabase 백업·수동 Fallback
```
