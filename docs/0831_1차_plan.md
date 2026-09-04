# 법률 사례 검색 AI Agent — 1차 개발 계획

> 문서 상태: 팀 회의용 1차 권고안  
> 목적: 팀원들이 빈 문서부터 논의하지 않고, 이 안을 기준으로 수정 의견을 제시한 뒤 개발 계약을 확정한다.  
> 개발 기간: 약 2.5일 / 팀원 4명 / 발표 약 20분

---

## 1. 프로젝트 한 줄 정의

사용자가 일상생활의 법률 문제를 자연어로 입력하면, AI Agent가 필요한 법령·사례 검색 Tool을 선택하고 MCP Server와 RAG를 통해 공식 근거와 유사 사례를 찾아 출처와 함께 설명하는 법률 정보 검색 서비스이다.

이 서비스는 법률 상담이나 승소 가능성 예측 서비스가 아니다. 검색된 자료에 근거한 정보 제공만 수행하며, 근거가 부족하면 추측하지 않는다.

---

## 2. MVP 범위

### 2.1 지원 카테고리 3개

1. **임대차·주거**
   - 전·월세 보증금 반환
   - 계약 종료 및 중도 해지
   - 임대인과의 분쟁
2. **근로·임금**
   - 임금 체불
   - 퇴직금 미지급
   - 부당해고 및 근로조건 불일치
3. **중고거래·소비자 분쟁**
   - 대금 지급 후 미배송
   - 설명과 다른 물품
   - 환불 거부 및 거래 사기 의심

카테고리를 벗어난 질문에는 무리하게 답하지 않고 현재 지원 범위와 관련 기관 또는 공식 검색 경로를 안내한다.

### 2.2 대표 시연 질문

개발과 발표는 아래 세 질문이 안정적으로 동작하는 것을 최우선 목표로 한다.

| 카테고리 | 대표 질문 | 기대 결과 |
|---|---|---|
| 임대차·주거 | 월세 계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다. | 관련 법령·조문, 유사 사례, 추가 확인사항 |
| 근로·임금 | 퇴직했는데 퇴직금을 받지 못했습니다. | 관련 법령·조문, 대응에 필요한 사실, 출처 |
| 중고거래·소비자 | 중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다. | 관련 근거·유사 사례, 민사/형사 단정 금지, 출처 |

### 2.3 기능 우선순위

#### MUST — 반드시 구현

- 카테고리 선택과 자연어 질문 입력
- Backend 질문 API
- 제한된 Agent Tool 선택 및 실행
- MCP Server와 법률 검색 Tool
- PostgreSQL + pgvector 기반 Hybrid Search
- 법령/사례 검색 결과 1~3개
- 검색된 근거만 이용한 LLM 답변
- 법령명·조문·사례·원문 출처 표시
- 검색 결과 없음, 외부 API/MCP/LLM 오류 처리
- Docker PostgreSQL과 Supabase를 `DATABASE_URL` 변경으로 전환
- 대표 질문 3개의 end-to-end 동작

#### SHOULD — MUST 완료 후 구현

- SSE 진행 상태 및 답변 스트리밍
- Redis 기반 최근 대화 문맥
- Agent/Tool 실행 Trace 표시
- 간단한 데모 로그인 또는 사용자 세션
- 평가 질문 10~15개를 이용한 검색 품질 측정

#### NICE TO HAVE — 시간이 남을 때만 구현

- 관리자 데이터 현황 화면
- 인기 검색어/FAQ 캐싱
- 음성 질문(STT)
- 검색어 자동완성
- 복수 LLM Provider

#### 이번 MVP에서 제외

- 모든 법률 분야 지원
- 승소 가능성 또는 판결 결과 예측
- 복잡한 회원가입·권한 시스템
- 법률 데이터 CRUD 관리자 기능
- 여러 Agent와 여러 MCP Server
- 영상 분석

---

## 3. 권장 시스템 구조

```text
Streamlit Frontend
    │ HTTP / SSE
    ▼
FastAPI Backend
    ├─ 요청 검증과 세션 관리
    ├─ Legal Agent 실행
    ├─ Redis 최근 대화 문맥(선택)
    ├─ MCP Client
    └─ 근거 기반 최종 답변 생성
            │ MCP
            ▼
Legal MCP Server
    ├─ search_legal_documents
    ├─ get_law_article
    └─ get_case_detail
            │
            ▼
RAG Service / Repository
    ├─ PostgreSQL + pgvector
    ├─ Keyword + Vector Hybrid Search
    └─ 외부 법률 API Adapter(선택)
```

### 계층별 책임과 금지사항

| 계층 | 책임 | 하지 않는 일 |
|---|---|---|
| Frontend | 입력, 진행 상태, 결과와 출처 표시 | DB·LLM·MCP 직접 접근 |
| Backend | HTTP, 세션, Agent Loop, MCP 호출, 최종 답변 | 법률 SQL 직접 작성, 출처 없는 지식 생성 |
| Agent | 질문을 보고 허용된 Tool·다음 행동·종료 선택 | 임의 함수 실행, 법률적 결론 확정 |
| MCP Tool | 표준 입력을 받아 검색/상세 조회 결과 반환 | 사용자용 최종 답변 작성 |
| RAG Service | Hybrid Search와 결과 순위화 | Tool 선택, LLM 답변 작성 |
| Repository | DB 질의와 결과 매핑 | Agent 정책 결정 |
| External Provider | 외부 API 호출과 응답 정규화 | 원본 응답을 상위 계층에 그대로 노출 |

---

## 4. 권장 폴더 구조

참고 프로젝트의 Router → Service → Agent/Tool → Repository 분리를 재사용하되, 학습용 Stage와 여러 Lab은 가져오지 않는다.

```text
aio-02-p2-team2/
├─ frontend/
│  ├─ app.py
│  ├─ pages/
│  ├─ components/
│  ├─ clients/
│  └─ core/
├─ backend/
│  └─ app/
│     ├─ main.py
│     ├─ routers/
│     ├─ schemas/
│     ├─ services/
│     ├─ agents/
│     ├─ mcp_clients/
│     └─ core/
├─ legal_mcp/
│  ├─ server.py
│  ├─ tools/
│  ├─ schemas/
│  ├─ services/
│  ├─ repositories/
│  └─ providers/
├─ database/
│  ├─ migrations/
│  ├─ seeds/
│  └─ scripts/
├─ tests/
│  ├─ contract/
│  ├─ integration/
│  └─ evaluation/
├─ docs/
├─ docker-compose.yml
├─ .env.example
├─ requirements.txt
└─ README.md
```

### 디렉터리 소유권

- 상옥: `frontend/`, 발표 자료 및 시연 시나리오
- 다혁: `backend/`
- 병훈: `legal_mcp/`
- 지혜: `database/`, RAG 관련 `legal_mcp/services`와 `repositories`
- 공동 수정: 루트 설정 파일, 공통 계약 문서, 통합 테스트
- 공동 파일 수정 전 팀 채널에 파일명과 목적을 공유한다.

---

## 5. 1차 API 계약

### 5.1 Backend 질문 API

`POST /api/legal/questions`

요청:

```json
{
  "session_id": "demo-session-001",
  "category": "labor",
  "message": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

`category` 허용값:

- `housing`: 임대차·주거
- `labor`: 근로·임금
- `consumer`: 중고거래·소비자 분쟁

응답:

```json
{
  "request_id": "req-uuid",
  "status": "completed",
  "category": "labor",
  "question_summary": "퇴직금 미지급 상황",
  "answer": "검색 근거를 바탕으로 정리한 답변",
  "laws": [],
  "cases": [],
  "sources": [],
  "follow_up_questions": [],
  "disclaimer": "이 답변은 법률 자문이 아닌 정보 제공이며 개별 사건의 결과를 보장하지 않습니다.",
  "trace": []
}
```

초기 개발에서는 일반 JSON 응답으로 전체 흐름을 먼저 완성한다. 이후 동일 결과 모델을 유지하면서 SSE를 추가한다.

### 5.2 상태 확인

`GET /health`

```json
{
  "status": "ok",
  "dependencies": {
    "mcp": "ok",
    "database": "ok",
    "redis": "disabled"
  }
}
```

### 5.3 SSE 이벤트 권고안

`POST /api/legal/questions/stream`

- `request_started`
- `context_loaded`
- `tool_selected`
- `retrieval_started`
- `retrieval_completed`
- `answer_generating`
- `answer_chunk`
- `completed`
- `error`

이벤트 payload에는 항상 `request_id`, `event`, `data`를 포함한다.

---

## 6. 1차 MCP Tool 계약

MVP Tool은 세 개로 제한한다. 모든 Tool 이름은 allowlist에 등록하고 Pydantic으로 입력을 다시 검증한다.

### 6.1 `search_legal_documents`

**목적:** 자연어 법률 상황과 의미적으로 관련된 법령·사례를 Hybrid Search로 조회한다.

**사용할 때:** 사용자가 일상 언어로 상황을 설명했거나 법령과 유사 사례를 함께 요청했을 때.

**사용하지 않을 때:** 법령명과 조문 번호가 정확히 주어져 원문 한 건만 조회하면 될 때.

입력:

```json
{
  "query": "퇴직 후 퇴직금을 받지 못한 상황",
  "category": "labor",
  "document_types": ["LAW", "CASE"],
  "top_k": 3
}
```

정책:

- `category`는 필수이며 세 허용값만 받는다.
- `top_k` 기본값은 3, 최댓값은 5이다.
- 검색어가 너무 짧거나 모호하면 실행하지 않고 검증 오류를 반환한다.

### 6.2 `get_law_article`

**목적:** 정확한 법령명과 조문 번호로 법률 원문과 메타데이터를 조회한다.

입력:

```json
{
  "law_name": "근로기준법",
  "article_number": "제36조"
}
```

**사용하지 않을 때:** 자연어 상황으로 관련 법률을 처음 탐색할 때.

### 6.3 `get_case_detail`

**목적:** 검색 결과로 얻은 내부 문서 ID 또는 사건번호의 상세 내용을 조회한다.

입력:

```json
{
  "document_id": "case-001"
}
```

**사용하지 않을 때:** 아직 검색 결과가 없거나 임의 사건번호를 추측해야 할 때.

### 6.4 공통 Tool 응답

성공:

```json
{
  "success": true,
  "data": {
    "items": []
  },
  "meta": {
    "query": "...",
    "result_count": 2,
    "retrieval_method": "hybrid"
  },
  "error": null
}
```

실패:

```json
{
  "success": false,
  "data": null,
  "meta": {},
  "error": {
    "code": "NO_RELEVANT_EVIDENCE",
    "message": "관련성이 충분한 자료를 찾지 못했습니다."
  }
}
```

### 6.5 공통 검색 결과 모델

```json
{
  "document_id": "law-001",
  "document_type": "LAW",
  "category": "labor",
  "title": "근로기준법 제36조",
  "summary": "검색 및 표시용 요약",
  "content": "근거가 되는 원문 또는 청크",
  "source_name": "국가법령정보센터",
  "source_url": "https://...",
  "effective_date": "YYYY-MM-DD",
  "score": 0.87,
  "metadata": {}
}
```

---

## 7. 1차 DB 및 RAG 설계

### 7.1 데이터 규모 권고안

짧은 일정에서 검색 품질을 확보하기 위해 다음을 1차 목표로 한다.

- 카테고리당 법령·조문 10~15건
- 카테고리당 판례 또는 공식 상담 사례 10~15건
- 전체 원본 문서 약 60~90건
- 카테고리당 평가 질문 5개, 총 15개

데이터 수가 부족하면 출처가 불명확한 데이터를 추가하기보다 검증된 자료를 적게 사용한다.

### 7.2 권장 테이블

#### `legal_documents`

- `id`: UUID 또는 안정적인 문자열 ID
- `document_type`: `LAW`, `CASE`, `GUIDELINE`
- `category`: `housing`, `labor`, `consumer`
- `title`
- `law_name`
- `article_number`
- `case_number`
- `court`
- `decided_at`
- `summary`
- `source_name`
- `source_url`
- `effective_date`
- `metadata`: JSONB
- `created_at`, `updated_at`

#### `legal_chunks`

- `id`
- `document_id`: `legal_documents.id` FK
- `chunk_index`
- `content`
- `token_count`
- `embedding`: vector
- `created_at`

원본 메타데이터와 검색 청크를 분리하여 하나의 법령·사례가 여러 청크로 나뉘어도 동일한 출처를 유지한다.

### 7.3 Chunking 권고안

- 법령: 조문 단위를 우선하며 너무 긴 조문만 문단 단위로 분리
- 판례/사례: 사건 개요, 판단 요지, 결론을 구분하되 판단 요지를 검색 중심으로 사용
- 초기값: 500~800 tokens, overlap 50~100 tokens
- 제목, 법령명, 조문 번호, 카테고리를 embedding 입력 앞부분에 함께 넣는다.

실제 값은 평가 질문 결과를 보고 조정한다.

### 7.4 Hybrid Search 권고안

1. `category`와 `document_type`으로 필터
2. 정확한 법령명·조문 요청은 SQL/Keyword 우선
3. 자연어 상황은 pgvector cosine similarity 사용
4. Keyword 점수와 Vector 점수를 정규화하여 결합
5. 동일 문서의 중복 청크 제거
6. 관련성 임계값 미달 결과 제거
7. 상위 3건 반환

초기 결합 점수 권고안:

```text
final_score = vector_score × 0.7 + keyword_score × 0.3
```

이는 확정값이 아니며 평가 질문 15개의 Top-3 결과로 조정한다.

### 7.5 검색 품질 완료 기준

- 평가 질문 15개 중 12개 이상에서 기대 문서가 Top 3에 포함
- 관련성 임계값이 낮은 질문은 빈 결과로 처리
- 모든 검색 결과가 원문 출처와 연결
- 같은 문서의 여러 청크가 최종 결과를 과도하게 차지하지 않음

---

## 8. 1차 Agent 정책

### 8.1 Agent가 결정하는 것

- 질문이 세 카테고리 중 어디에 해당하는지 확인
- 어떤 MCP Tool이 필요한지 선택
- 검색 결과를 보고 상세 조회가 필요한지 결정
- 근거가 충분한지 또는 추가 질문이 필요한지 결정
- 최대 호출 수 안에서 종료

사용자가 UI에서 카테고리를 명시한 경우 Agent는 이를 우선 사용하되, 질문과 명백히 충돌하면 확인 질문을 한다.

### 8.2 Backend가 강제로 통제하는 것

- Tool allowlist
- Pydantic 입력 검증
- 카테고리 허용값
- `top_k` 제한
- Tool 최대 호출 횟수
- Timeout
- Tool 오류 표준화
- 출처 없는 근거 제외
- 최종 응답 Schema 검증

### 8.3 실행 제한 권고안

- Tool 최대 호출: 3회
- 동일 Tool의 동일 인자 중복 호출 금지
- 전체 요청 Timeout: 60초
- MCP 호출 Timeout: 15초
- 검색 결과가 없으면 검색어를 한 번만 보완하여 재검색
- 두 번째 검색도 실패하면 추측하지 않고 추가 정보 요청

### 8.4 최종 답변 형식

1. 상황 요약
2. 관련 법률과 조문
3. 유사 사례
4. 현재 정보로 판단하기 어려운 점
5. 사용자가 추가로 확인할 사실
6. 출처
7. 법률 정보 제공 고지

### 8.5 Hallucination 방지 지침

- Tool Result에 없는 법령, 조문, 사건번호를 생성하지 않는다.
- 모든 법률 주장은 하나 이상의 `document_id`와 연결한다.
- 근거가 부족하면 명시적으로 부족하다고 답한다.
- 위법 여부, 범죄 성립, 승소 가능성을 단정하지 않는다.
- 출처의 시행일과 사건별 사실관계 차이를 알린다.
- 검색 자료와 사용자의 진술을 구분한다.

---

## 9. Redis, SSE, 로그인 1차 결정

### 9.1 Redis

MUST 전체 흐름이 완성된 후 적용한다.

- 용도: 최근 대화 5개 또는 최근 20분 문맥 저장
- Key 예시: `legal:session:{session_id}:messages`
- TTL 권고: 30분
- 저장 대상: 사용자 질문, 카테고리, 상황 요약, 답변 요약
- 저장 금지: API Key, 비밀번호, 불필요한 개인정보 원문
- Redis 장애 시 대화 문맥 없이 현재 질문만 처리하도록 degrade

### 9.2 SSE

- 먼저 일반 JSON API를 완성한 후 추가
- 검색 및 생성 상태를 사용자에게 표시
- 가능하면 `answer_chunk`로 답변도 스트리밍
- 시간이 부족하면 상태 이벤트만 보내고 최종 답변은 한 번에 전송

### 9.3 로그인

- 1차 권고: 정식 회원가입은 제외
- `session_id` 기반 데모 사용자 또는 고정 데모 계정 사용
- MUST 기능 완료 후 시간이 남으면 간단한 사용자 구분만 추가
- 발표에서는 인증 확장 지점과 개인정보 최소 수집 원칙을 설명

---

## 10. 환경변수 1차 목록

Frontend와 서버 환경변수를 분리한다. API Key는 Frontend에 두지 않는다.

```env
# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
LLM_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=
MCP_SERVER_URL=http://127.0.0.1:8001
REDIS_URL=redis://127.0.0.1:6379/0
REQUEST_TIMEOUT_SECONDS=60
MAX_TOOL_CALLS=3

# MCP / DB
MCP_HOST=0.0.0.0
MCP_PORT=8001
DATABASE_URL=postgresql+psycopg://...
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
LEGAL_API_BASE_URL=
LEGAL_API_KEY=
RETRIEVAL_TOP_K=3
RETRIEVAL_SCORE_THRESHOLD=

# Frontend 전용
BACKEND_API_URL=http://127.0.0.1:8000
```

실제 비밀값은 `.env`에 두고 `.env.example`에는 이름과 안전한 기본값만 작성한다.

---

## 11. 공통 오류 코드

| 코드 | 의미 | 사용자 처리 |
|---|---|---|
| `INVALID_REQUEST` | 요청 Schema 오류 | 입력 확인 안내 |
| `UNSUPPORTED_CATEGORY` | 미지원 카테고리 | 지원 범위 표시 |
| `TOOL_NOT_ALLOWED` | 허용되지 않은 Tool | 일반 오류 처리 및 로그 |
| `TOOL_VALIDATION_ERROR` | Tool 인자 오류 | 추가 질문 또는 입력 수정 |
| `MCP_UNAVAILABLE` | MCP 연결 실패 | 잠시 후 재시도 안내 |
| `DATABASE_ERROR` | DB 검색 실패 | 시스템 오류 안내 |
| `EXTERNAL_API_ERROR` | 외부 API 오류 | 자체 DB 결과 사용 또는 오류 표시 |
| `NO_RELEVANT_EVIDENCE` | 충분한 근거 없음 | 추가 사실 질문 |
| `LLM_TIMEOUT` | LLM 시간 초과 | 재시도 안내 |
| `INTERNAL_ERROR` | 미분류 서버 오류 | 요청 ID와 함께 오류 표시 |

Mock 결과를 실제 결과처럼 조용히 반환하지 않는다. Demo/Mock 모드를 사용한다면 화면과 응답에 명확히 표시한다.

---

## 12. 역할별 작업 배분과 예상 소요시간

### 산정 기준

- 개인별 핵심 작업을 **약 16시간**으로 맞춘다.
- 공통 회의, Git merge 대기, 점심시간, 전체 발표 리허설은 개인 작업시간에서 제외한다.
- 추정치는 숙련도와 외부 API 상태에 따라 약 ±20% 변동할 수 있다.
- 다른 팀원의 완료를 기다리는 시간에는 Mock 계약을 사용해 병렬 개발한다.

### 12.1 상옥 — Frontend + 팀장 + 발표: 총 16시간

| 작업 | 예상 |
|---|---:|
| 화면 구조, 사용자 흐름, 컴포넌트 설계 | 1.5h |
| 카테고리·질문 입력·데모 질문 UI | 1.5h |
| Backend Client와 JSON 응답 연동 | 2.0h |
| 답변·법령·사례·출처 카드 UI | 2.5h |
| 로딩·빈 결과·오류·재시도 UX | 1.0h |
| SSE 또는 진행 상태 UI | 1.5h |
| 통합 시나리오 확인 및 Frontend 수정 | 1.5h |
| 아키텍처 그림과 발표자료 핵심 슬라이드 | 2.0h |
| 시연 대본·영상 녹화 주도 | 1.5h |
| 20분 발표 원고·개인 리허설 | 1.0h |
| **합계** | **16.0h** |

완료 기준:

- 대표 질문 3개를 입력하고 결과와 출처를 읽을 수 있다.
- Backend 지연, 빈 결과, 실패 상태가 화면에 구분된다.
- 발표자료에서 전체 데이터 흐름과 각 기술의 사용 이유를 설명할 수 있다.

### 12.2 다혁 — Backend + Agent: 총 16시간

| 작업 | 예상 |
|---|---:|
| FastAPI 구조·설정·공통 Schema | 1.5h |
| 질문 API와 응답 모델 | 2.0h |
| MCP Client와 오류/Timeout 처리 | 2.0h |
| Legal Agent instructions와 Tool 선택 | 2.5h |
| 최대 3회 Agent Loop·중복 호출 방지 | 2.5h |
| Tool Result 기반 구조화 답변 생성 | 2.0h |
| 근거 ID·출처 검증과 환각 방지 | 1.0h |
| SSE 구현 | 1.0h |
| Redis 최근 문맥 또는 JSON API 보강 | 0.5h |
| Backend 단위·통합 테스트 및 디버깅 | 1.0h |
| **합계** | **16.0h** |

시간 부족 시 Redis를 먼저 제외하고 Agent 안정성과 출처 검증에 시간을 사용한다.

완료 기준:

- 허용된 MCP Tool만 최대 3회 호출한다.
- MCP/LLM 장애와 근거 없음 상태가 공통 오류로 반환된다.
- 최종 답변의 법률 근거가 Tool Result의 `document_id`에 연결된다.

### 12.3 병훈 — MCP Server + Tool + 외부 API: 총 16시간

| 작업 | 예상 |
|---|---:|
| MCP Server 골격과 health 확인 | 1.5h |
| 공통 Tool 입력·출력 Schema | 1.0h |
| `search_legal_documents` Tool | 2.5h |
| `get_law_article` Tool | 1.5h |
| `get_case_detail` Tool | 1.5h |
| Tool registry·allowlist·검증·오류 표준화 | 2.0h |
| 외부 법률 API 조사 및 Adapter | 2.0h |
| API 응답 → 공통 LegalDocument 변환 | 1.5h |
| DB/RAG Service 연동 | 1.5h |
| Tool description 문서화 | 0.5h |
| MCP 계약·통합 테스트 및 장애 처리 | 0.5h |
| **합계** | **16.0h** |

외부 API 사용 승인이 늦거나 품질이 낮으면 Adapter 골격까지만 만들고 자체 DB를 시연 기준으로 사용한다.

완료 기준:

- 세 Tool의 description에 목적, 사용 조건, 금지 조건, 입력, 출력이 명확하다.
- 모든 Tool이 동일한 성공/오류 envelope를 반환한다.
- 외부 API 원본 형식이 MCP 밖으로 노출되지 않는다.

### 12.4 지혜 — DB + RAG: 총 16시간

| 작업 | 예상 |
|---|---:|
| PostgreSQL/pgvector Docker 구성 | 1.5h |
| Supabase 프로젝트·연결 전환 확인 | 0.5h |
| Migration과 테이블·인덱스 | 1.5h |
| 세 카테고리 데이터 수집·정제 | 2.5h |
| Seed/적재 스크립트 | 1.5h |
| Chunking·Embedding 파이프라인 | 2.0h |
| Vector Search | 1.5h |
| Keyword 및 Hybrid Search | 2.0h |
| 중복 제거·필터·임계값 처리 | 1.0h |
| 평가 질문 15개와 검색 품질 조정 | 1.5h |
| Repository 계약 테스트·데이터 설명 문서 | 0.5h |
| **합계** | **16.0h** |

데이터 수집이 예상보다 길어지면 문서 수를 줄이고 각 카테고리의 대표 질문과 직접 관련된 검증된 자료를 우선한다.

완료 기준:

- Docker와 Supabase가 같은 Schema와 Repository 코드로 동작한다.
- 모든 문서가 출처와 연결된다.
- 평가 질문 15개 중 최소 12개에서 기대 문서가 Top 3에 포함된다.

### 12.5 교차 리뷰 담당

| 산출물 | 작성자 | 1차 리뷰어 |
|---|---|---|
| Frontend 응답 표시 | 상옥 | 다혁 |
| Backend–MCP 계약 | 다혁 | 병훈 |
| MCP–RAG 계약 | 병훈 | 지혜 |
| DB Schema·검색 결과 모델 | 지혜 | 병훈 |
| 발표 아키텍처와 기술 설명 | 상옥 | 전원 |

리뷰는 코드 전체를 대신 구현하는 것이 아니라 계약 불일치, 누락, 시연 위험을 확인하는 20~30분 단위 활동으로 진행한다.

---

## 13. 2.5일 통합 일정

### Day 1 오전 — 계약 확정과 Mock 병렬 개발

공동 목표:

- 이 문서에 대한 수정 의견 반영
- API, MCP Tool, LegalDocument Schema 확정
- 대표 질문과 기대 문서 확정
- `.env.example`, 포트, 브랜치 확정

개인 목표:

- 상옥: Mock JSON으로 전체 화면 골격
- 다혁: Backend 질문 API와 Mock MCP Client
- 병훈: MCP Server와 세 Tool의 Mock 응답
- 지혜: Docker DB, Schema, 최소 seed

**통합 Checkpoint 1:** 점심 전 Backend → Mock MCP 호출, Frontend → Backend 호출 확인.

### Day 1 오후 — 첫 end-to-end 완주

- 상옥: 실제 응답 모델과 결과 카드 연결
- 다혁: Agent 선택 → MCP 호출 → 답변 생성
- 병훈: MCP Tool → Repository 연결
- 지혜: 데이터 적재 → Vector Search 연결

**통합 Checkpoint 2:** 오후 중간에 임대차 대표 질문 한 건을 전체 흐름으로 성공.

**Day 1 종료 기준:** 세 카테고리 중 최소 한 카테고리에서 질문 → Agent → MCP → DB → 답변 → 출처 표시가 동작한다.

### Day 2 오전 — 세 카테고리와 품질

- 세 대표 질문 모두 end-to-end 연결
- Hybrid Search 품질 조정
- 근거 부족 및 오류 처리
- Tool description과 Agent instruction 보강
- Docker/Supabase 전환 확인
- MUST 항목 완료 선언

**통합 Checkpoint 3:** 점심 전에 세 대표 질문을 순서대로 실행하고 실패 목록 작성.

### Day 2 오후 — 기능 동결과 발표 준비

- SHOULD 기능은 여유 시간에만 추가
- 통합·회귀 테스트
- 시연용 데이터와 결과 고정
- 시연영상 녹화
- README와 아키텍처 자료
- 최종 merge

**기능 동결 시점:** Day 2 오후 중간. 이후에는 치명적 오류 외 신규 기능을 추가하지 않는다.

**Day 2 종료 기준:** 새 환경에서 README대로 실행 가능하고 시연영상이 저장되어 있다.

### Day 3 오전 — 검증과 발표

- 세 대표 질문 최종 확인
- 외부 API 장애 시나리오 확인
- 20분 발표 리허설 2회
- 발표 시간 초과 부분 제거
- 시연영상과 실제 시연 중 선택 기준 확정

---

## 14. Git 협업 규칙

### 브랜치

```text
main
└─ develop
   ├─ feature/frontend
   ├─ feature/backend-agent
   ├─ feature/mcp
   └─ feature/rag-db
```

- `main`: 발표 가능한 버전만 유지
- `develop`: 통합 브랜치
- 개인 feature 브랜치는 매 통합 전에 `develop` 최신 변경을 반영
- 직접 `main`에 push하지 않는다.

### Commit 권고

- 한 커밋에는 한 목적만 포함
- 동작하지 않는 큰 덩어리보다 작은 단위로 자주 commit
- 예시:
  - `feat(frontend): add legal category selector`
  - `feat(agent): add bounded mcp tool loop`
  - `feat(mcp): implement legal document search tool`
  - `feat(rag): add pgvector hybrid search`
  - `fix(contract): align legal document response schema`

### Merge 규칙

- 점심 전, Day 1 종료 전, Day 2 점심 전, 기능 동결 전에 통합
- 공통 Schema 변경은 PR/merge 전에 네 명에게 공유
- 충돌을 해결할 때 상대 파일을 임의로 삭제하지 않는다.
- merge 후 대표 질문 최소 한 건을 즉시 실행한다.

---

## 15. 테스트 및 완료 기준

### 15.1 계약 테스트

- Backend가 예상된 MCP 요청 Schema를 전송하는가
- MCP가 공통 Tool 응답 Schema를 지키는가
- Repository 결과가 LegalDocument 모델로 변환되는가
- Frontend가 Backend 성공·빈 결과·오류 응답을 표시하는가

### 15.2 통합 테스트

- 세 대표 질문 성공
- 카테고리 밖 질문
- 모호한 질문
- 검색 결과 없음
- MCP 서버 종료
- DB 연결 실패
- LLM Timeout
- 출처 URL 누락 데이터

### 15.3 프로젝트 Definition of Done

다음 조건을 모두 만족해야 MVP 완료로 본다.

- 세 카테고리의 대표 질문이 end-to-end로 동작한다.
- 답변의 법률 근거와 출처가 실제 검색 결과에 존재한다.
- 근거가 없는 경우 추측하지 않는다.
- Agent Tool 호출이 allowlist와 최대 횟수로 제한된다.
- Docker DB와 Supabase가 환경변수 변경으로 전환된다.
- 새 PC 또는 새 가상환경에서 README 순서로 실행할 수 있다.
- 시연영상과 발표자료가 준비되어 있다.
- 팀원 전원이 자기 계층의 책임과 설계 이유를 설명할 수 있다.

---

## 16. 발표 20분 권고 구성

| 구간 | 시간 | 내용 |
|---|---:|---|
| 문제와 서비스 정의 | 2분 | 법률 정보 탐색의 어려움, AI 변호사가 아님을 설명 |
| 사용자 시연 | 4분 | 대표 질문, Tool/RAG 진행, 출처 포함 답변 |
| 시스템 아키텍처 | 4분 | Frontend → Backend → Agent → MCP → RAG/DB |
| Agent·Tool·MCP 설계 | 4분 | 왜 Agent인지, Tool 분리와 제한, 상세 description |
| DB·RAG·검색 평가 | 3분 | Hybrid Search, pgvector, 데이터 출처, Top-3 평가 |
| 안전성·한계·확장 | 2분 | 환각 방지, 법률 고지, 미지원 범위 |
| 마무리 | 1분 | 핵심 성과 요약 |

질의응답 시간이 발표 20분에 포함된다면 본 발표를 15~16분으로 줄인다.

---

## 17. 팀 회의에서 수정 의견을 받을 항목

각 팀원은 아래 형식으로 의견을 남긴다.

```text
[이름]
- 대상 항목:
- 현재 안:
- 변경 제안:
- 변경 이유:
- 예상 영향(시간/API/다른 팀원):
```

반드시 확인할 항목:

1. 세 카테고리와 세 대표 질문이 적절한가
2. 실제 확보 가능한 법률 데이터 출처와 문서 수는 얼마인가
3. MCP Tool 세 개로 충분한가
4. Backend와 MCP가 사용할 MCP transport는 무엇인가
5. 사용할 LLM과 Embedding 모델은 무엇인가
6. Supabase 프로젝트와 외부 법률 API 사용 권한이 준비됐는가
7. SSE와 Redis 중 시간 부족 시 무엇을 우선할 것인가
8. 각자 16시간 작업량이 실제 숙련도에 맞는가
9. 발표에서 실시간 시연과 녹화 영상을 어떻게 나눌 것인가

---

## 18. 회의 후 즉시 확정해야 하는 값

아래 값이 정해져야 구현 중 재논의를 줄일 수 있다.

```text
LLM_PROVIDER=
LLM_MODEL=
EMBEDDING_PROVIDER=
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
MCP_TRANSPORT=
LEGAL_DATA_SOURCES=
RETRIEVAL_TOP_K=3
RETRIEVAL_SCORE_THRESHOLD=
REDIS_ENABLED=
SSE_ENABLED=
DEMO_LOGIN_ENABLED=
FEATURE_FREEZE_TIME=
```

이 문서는 1차 기준안이다. 팀 의견 반영 후 API/MCP/DB 계약 부분을 먼저 확정하고, 확정된 계약은 통합 전까지 임의로 변경하지 않는다.
