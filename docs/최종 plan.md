# 생활 법률 검색 AI Agent 최종 개발 계획 v2

> 버전: v2.0  
> 작성일: 2026-09-05  
> 이전 버전: `docs/회의내용/0905_최종 plan.md`
> 범위: 전체 프로젝트

## 1. v1에서 수정된 점

| 구분 | v1 | v2 |
|---|---|---|
| 실행 | 논리 계층 | 담당자 4대 PC 서버 |
| DB | PostgreSQL | DB PC Docker PostgreSQL Primary |
| Supabase | 미확정 | 백업·외부 통합·수동 Fallback |
| 역할 | 익명 중심 | 비회원·회원·관리자 |
| FAQ | 조회형 | 공지 FAQ + 최신 사용자 질문 게시판·CRUD·페이지네이션 |
| 이력 | 저장하기 중심 | 사례·FAQ 통합, 비회원 7일·회원 영구 |
| 인증 | 후순위 | Backend + Redis Session 권장 |
| Redis | 문맥·Cache | DB PC 운영, Backend/MCP 분리 사용 |
| 장애 | 일반 오류 | 저하 운영과 수동 Fallback |

Frontend 로컬 Mock의 진행 내용은 `docs/프론트엔드 진행상황 공유.md`에서 별도 관리한다.

## 2. 전체 목표

- 세 전문 Agent
- 공식 법령·판례와 Source URL
- Hybrid Search와 Top 3
- 근거 기반 답변과 안전정책
- 비회원·회원·관리자 권한
- FAQ·질의 이력 CRUD
- 네 PC 전체 E2E
- Supabase 백업·Fallback

## 3. 목표 구조

```text
Frontend PC → Backend PC
                ├→ MCP PC → DB PC PostgreSQL
                └→ DB PC PostgreSQL·Redis

DB PC → Supabase 백업·수동 Fallback
```

Frontend는 Backend만 호출하고, 법률 검색은 MCP를 경유한다. 사용자·FAQ·이력 CRUD는 Backend가 담당한다.

## 4. 파트별 책임

| 파트 | 책임 |
|---|---|
| Frontend | 화면, 역할 UX, Backend Client, 오류 표시 |
| Backend | API, Agent, Auth, 소유권, FAQ·이력 CRUD |
| MCP | Legal Tool, Hybrid Search, 검색 Cache |
| DB | PostgreSQL·pgvector·Redis, Migration, 수집·Embedding |
| Supabase | 백업·외부 통합·수동 Fallback |

## 5. 데이터 정책

- 공식 법률 데이터와 명시적으로 저장한 질문만 PostgreSQL에 보관한다.
- 비회원 질문은 작성일 기준 7일 보관한다.
- 회원 질문은 안내와 동의 후 영구보관한다.
- 공개 동의를 받은 질문은 FAQ 아래 사용자 질문 게시판에 최신순으로 표시한다.
- 비공개 질문과 개인정보가 포함된 내용은 공개 목록에 표시하지 않는다.
- Redis는 Session·Agent 상태·문맥·Cache이며 영구 원본이 아니다.
- Docker와 Supabase에 동시에 쓰지 않는다.

## 6. 핵심 Schema

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

필수 제약:

- 공식 문서 외부 ID Unique
- 문서별 Chunk Index Unique
- 회원 또는 비회원 소유자 하나만 존재
- category·document_type Check
- 질문·답변·출처 관계 보장

## 7. 데이터 구축과 검색

```text
Open API → Normalize → content_hash Upsert
→ Chunk → Embedding → PostgreSQL + pgvector
```

```text
category/document_type filter
→ Keyword + Vector
→ Score 결합
→ 중복 제거
→ Threshold
→ Top 3
```

카테고리별 질문 5개, 총 15개 검색 평가를 수행한다.

## 8. 역할·인증·FAQ

- `GUEST`: 공개 질문 조회, 본인 질문 7일 CRUD
- `USER`: 공개 질문 조회, 본인 질문 영구, 여러 기기 조회
- `ADMIN`: 공지 FAQ 관리와 운영정보
- 인증은 Backend가 HttpOnly Cookie와 Redis Session으로 처리한다.
- 관리자도 사용자 원문은 기본적으로 조회하지 않는다.
- 답변 완료 질문은 수정하지 않고 새 질문으로 재분석한다.
- 사용자 질문 목록은 `created_at DESC, id DESC` 최신순과 서버 페이지네이션을 사용한다.
- 기본 `page_size=10`, 최대 50으로 제한한다.

## 9. Docker와 Supabase

### Docker PostgreSQL

- 네 PC 통합의 Primary
- 애플리케이션 읽기·쓰기
- 내부망·오프라인 시연

### Supabase

- 검증된 Snapshot
- 외부 통합 확인
- DB PC 장애 시 수동 Fallback
- 초기 Fallback은 읽기 중심

Migration은 한 곳에서만 관리해 양쪽에 동일하게 적용한다.

## 10. 개발 단계

### 1단계: 계약 확정

- 실제 IP·Port·방화벽
- API·ToolResult·오류코드
- Schema·Migration
- 인증·Cookie·Redis
- Supabase 정책

### 2단계: DB PC

- Docker PostgreSQL + pgvector
- Redis
- Migration·Seed·계정·Health Check

### 3단계: MCP PC

- DB 연결
- `search_cases` 우선
- 나머지 Tool과 Cache

### 4단계: Backend PC

- MCP Client
- LaborAgent Loop
- 오류·Trace·Health

### 5단계: Frontend 연결

- API Mode
- View Model 호환
- 로딩·오류·no-evidence

### 6단계: 사용자 기능

- 인증·역할·소유권
- FAQ·질의 이력 CRUD
- 공개 사용자 질문 최신순 목록과 페이지네이션
- 만료·영구보관

### 7단계: 확장·운영

- 세 Agent
- 검색평가·안전성
- Supabase 백업·Fallback
- 장애 테스트

## 11. 첫 통합 목표

```text
Frontend PC 퇴직금 질문
→ Backend PC LaborAgent
→ MCP PC search_cases
→ DB PC pgvector
→ 공식 판례 Top 3
→ Frontend 표시
```

이 경로가 성공한 후 세 Agent와 인증을 확장한다.

## 12. 테스트

- 파트별 Unit Test
- Frontend–Backend 계약
- Backend–MCP 계약
- MCP–DB 계약
- 대표 질문 3개 E2E
- 권한·소유권·만료
- 법률 안전성
- Redis·MCP·DB 장애
- Supabase Fallback과 복구

## 13. 완료 기준

- 네 PC Health Check
- 공식 출처와 Top 3
- Evidence 기반 답변
- 역할별 FAQ·이력
- 비회원 7일·회원 영구보관
- 다른 사용자 접근 차단
- Redis 장애 중 핵심 검색
- Supabase 백업·수동 Fallback
- 전체 테스트와 README

## 14. Issue·PR 분리

1. 분산 서버·환경변수 계약
2. PostgreSQL·Redis
3. Schema·Seed
4. MCP 검색
5. Backend Agent E2E
6. 인증·역할
7. FAQ·질의 이력
8. Frontend API 연결
9. 검색평가·안전성
10. Supabase 백업·Fallback

PR 제목은 한글로 작성하고 공통 계약 변경은 관련 담당자가 함께 검토한다.

## 15. 팀 회의 체크리스트

- 실제 IP·Port·방화벽
- JSON·오류코드·Timeout
- Migration 원본과 DB 권한
- Redis Key·TTL·장애정책
- Cookie와 로그인 유지기간
- 비회원 보관 동의
- 관리자 범위와 Audit
- Supabase 백업 범위·주기
- 장애 전환·복구 담당

## 16. 최종 일정 원칙

```text
계약 → DB → MCP → LaborAgent → Frontend 연결
→ 인증·FAQ·이력 → 세 Agent → 백업·장애 테스트
```
