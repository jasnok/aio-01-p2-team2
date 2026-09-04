# 생활 법률 검색 AI Agent 최종 개발 계획

> 버전: MVP v1.0
>
> 확정일: 2026-09-04
>
> 데이터 기준일: 2026-09-04

이 문서는 09.04 회의에서 합의된 사항과 합의가 필요한 추천안을 함께 정리한 팀 계약서 초안이다. `확정`은 회의에서 합의된 내용, `추천 확정안`은 구현 충돌을 막기 위해 본 문서가 제안하는 기본값, `팀 확인 필요`는 담당자 참석 후 결정할 내용을 뜻한다. 추천 확정안은 팀 공유 후 이견이 없을 때 Team Contract v1로 승인한다.

## 1. 프로젝트 정의

사용자가 임대차·주거, 근로·임금, 소비자·중고거래 상황을 자연어로 입력하면 전문 Agent가 적절한 법령·판례 검색 Tool을 선택하고, Legal MCP Server가 PostgreSQL + pgvector에서 공식 근거를 검색하여 이해하기 쉬운 정보를 제공하는 서비스다.

이 서비스는 법률 자문, 범죄 성립 판단 또는 승패 예측 서비스가 아니다.

## 2. 오늘 확정 결과

| 항목 | 상태 | 확정 내용 |
|---|---|---|
| DB 자료 구조 및 Schema | 추천 확정안 | 7개 핵심 테이블과 ID·제약조건 사용, 팀 승인 필요 |
| Mock 데이터 검색 테스트 | 계획 확정 | 이번 주 15개 질문, Top-3 적중 12개 이상 목표 |
| Open API 영속 저장 | 확정 | 승인받은 데이터는 PostgreSQL에 사전 저장 가능, 이용조건 준수 |
| Open API 호출 방식 | 확정 | 사용자 요청 시 실시간 호출이 아닌 사전 수집 기본 |
| Open API 갱신 방식 | 확정 | `external_id + content_hash` 기반 Upsert |
| 데이터 소스 | 완료 | 국가법령정보 공동활용 Open API |
| MCP Tool I/O 초안 | 완료 | 3개 읽기 Tool과 공통 ToolResult 계약 |
| MCP Server 분리 | 완료 | Legal MCP Server 1개, 내부 계층 분리 |
| Frontend Flow | 예시 화면 기준 확정 | 사례 분석 중심 결과 화면과 기능별 사이드바를 결합 |
| Frontend 디자인 | 예시 화면 기준 확정 | `docs/회의내용/0903_프론트엔드예시화면.png`의 LawPath 대시보드 구조 사용 |
| AI Agent 명세서 | 생성 | `docs/AI agent 명세서.md` |
| Agent·검색 테스트 | 계획 확정 | 자동화 테스트와 `tests/evaluation` 결과로 관리 |

## 3. 확정 시스템 구조

```text
Streamlit Frontend
→ FastAPI Backend
→ AgentRegistry
→ 전문 AgentProfile + 공통 AgentRuntime
→ Legal MCP Client
→ Legal MCP Server
→ Service
→ Repository
→ PostgreSQL + pgvector
```

데이터 구축 흐름은 사용자 요청과 분리한다.

```text
국가법령정보 공동활용 Open API
→ Raw 응답 수집
→ Normalize
→ PostgreSQL legal_documents
→ Chunking
→ Embedding
→ PostgreSQL legal_chunks + pgvector
```

## 4. 역할과 책임

| 담당 | 역할 |
|---|---|
| 상옥 | Frontend, Streamlit, 팀 리드, 발표·시연 |
| 다혁 | Backend, Agent, LLM Provider |
| 병훈 | Legal MCP Server, Tool, Service/Repository 연동 |
| 지혜 | PostgreSQL, pgvector, 수집·정규화·Embedding·Redis |

공통 계약 변경은 단독으로 확정하지 않고 관련 담당자와 공유한다.

## 5. 지원 범위

```text
housing  → HousingAgent
labor    → LaborAgent
consumer → ConsumerAgent
```

대표 질문:

1. 계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다.
2. 퇴직했는데 퇴직금을 받지 못했습니다.
3. 중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다.

## 6. Team Contract v1

아래 값은 파트별 구현이 서로 달라지는 것을 막기 위한 추천 확정안이다. 팀 공유 후 승인하고, 변경 시 관련 담당자에게 알린 뒤 본 문서를 먼저 갱신한다.

### 6.1 공통 코드값

```text
CATEGORY: housing, labor, consumer
DOCUMENT_TYPE: LAW, CASE, GUIDELINE
SOURCE_TYPE: law, case, external
```

### 6.2 ID 정책

```text
id
→ PostgreSQL 내부 BIGSERIAL PK

external_id
→ 국가법령정보 공동활용에서 받은 원천 식별자

document_id
→ MCP/API에서 사용하는 문자열형 내부 문서 ID
→ MVP에서는 legal_documents.id를 문자열로 변환하여 사용
```

외부 ID는 `UNIQUE(source_name, external_id)`로 보호한다.

실행과 사용자 관련 ID는 다음처럼 구분한다.

```text
user_id
→ 사용자를 식별하는 DB 내부 ID

session_id
→ 비로그인 사용자의 일시적인 브라우저 세션 ID

request_id 또는 run_id
→ 질문 한 건에 대한 Agent 실행 ID(UUID)

agent_id
→ housing, labor, consumer 중 선택된 Agent ID
```

`request_id`와 `run_id`는 MVP에서 같은 UUID 값을 사용한다. DB PK는 관계와 정렬이 단순한 `BIGSERIAL`, 외부에 노출되는 실행·세션 ID는 UUID 문자열을 사용한다.

### 6.3 질문 API

```http
POST /api/legal/questions
```

```json
{
  "session_id": "web-uuid",
  "category": "labor",
  "question": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

MVP에서는 category를 필수로 받고 자동 분류는 후순위로 둔다.

### 6.4 핵심 응답

```text
request_id
agent_id
status
termination_reason
question_summary
answer
related_laws
similar_cases
sources
follow_up_questions
cautions
is_mock
```

Trace는 일반 사용자 응답에서 제외하고 테스트 API 또는 운영 로그에 둔다.

## 7. DB Schema 확정

### 7.1 `users`

사용자 테이블 생성은 회의에서 합의했다. 로그인 기능은 합의되지 않았으므로 MVP에서는 복잡한 로그인 없이 익명 사용자를 지원하는 방식을 추천 확정안으로 사용한다.

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    anonymous_key VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.2 `legal_documents`

```sql
CREATE TABLE legal_documents (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) NOT NULL,
    document_type VARCHAR(20) NOT NULL
        CHECK (document_type IN ('LAW', 'CASE', 'GUIDELINE')),
    category VARCHAR(20) NOT NULL
        CHECK (category IN ('housing', 'labor', 'consumer')),
    title TEXT NOT NULL,
    law_name TEXT,
    article_number VARCHAR(50),
    case_number VARCHAR(100),
    case_name TEXT,
    court VARCHAR(100),
    decided_at DATE,
    judgment_result TEXT,
    summary TEXT,
    content TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    effective_date DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_name, external_id)
);
```

MVP에서는 문서 하나에 category 하나를 부여한다. 다중 카테고리 관계 테이블은 검색 평가에서 실제 필요성이 확인될 때 추가한다.

### 7.3 `legal_chunks`

MVP Embedding은 비용과 구현 단순성을 고려해 OpenAI `text-embedding-3-small`, 1,536차원으로 확정한다.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE legal_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL
        REFERENCES legal_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding VECTOR(1536),
    embedding_model VARCHAR(100) NOT NULL,
    embedding_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);
```

DB 적재와 MCP Query Embedding은 모두 `text-embedding-3-small`, 1,536차원을 사용한다. 환경변수는 `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_DIMENSION=1536`으로 통일한다. 모델을 변경할 때는 별도 Migration과 전체 재임베딩을 수행한다.

### 7.4 `ingestion_runs`

```sql
CREATE TABLE ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    document_type VARCHAR(20),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
```

### 7.5 사용자 저장 테이블

```sql
CREATE TABLE saved_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    source_request_id VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE saved_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES saved_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE saved_message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL
        REFERENCES saved_messages(id) ON DELETE CASCADE,
    document_id BIGINT REFERENCES legal_documents(id),
    chunk_id BIGINT REFERENCES legal_chunks(id),
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (message_id, document_id, chunk_id)
);
```

사용자가 `저장하기`를 누른 경우에만 질문, 답변과 사용된 근거를 하나의 PostgreSQL Transaction으로 저장한다. `source_request_id`로 중복 저장을 방지한다. 이 저장 Flow는 추천 확정안이며, 로그인 도입 여부와 함께 팀 확인 후 구현한다.

## 8. 데이터와 개인정보 정책

PostgreSQL:

- 공식 법령·판례 원문과 메타데이터
- Chunk와 Embedding
- 수집 이력
- 사용자가 명시적으로 저장한 질문·답변과 근거

Redis:

- 최근 대화 5~10개, 약 30분 TTL
- 요청 상태
- Tool Timeline
- 검색 Cache

저장 금지:

- API Key, 비밀번호, DB 연결 문자열, Authorization Header
- 전체 System Prompt와 LLM 내부 추론
- 불필요한 주민등록번호, 계좌번호 등 개인정보
- 사용자가 저장을 요청하지 않은 장기 질문 이력

Redis 장애 시 최근 문맥·Cache 기능만 제한하고 PostgreSQL 법률 검색은 계속 동작한다.

## 9. Open API 영속 저장 결정

### 9.1 결론

국가법령정보 공동활용 이용안내는 제공 법령정보가 공공데이터 정책에 따라 개방되고, 영리 목적을 포함한 자유로운 활용이 보장된다고 안내한다. 따라서 승인받은 API 데이터를 프로젝트 PostgreSQL에 정규화하여 영속 저장하는 방식으로 확정한다.

준수 조건:

- 공동활용 신청과 승인 후 사용
- 승인받은 API와 이용 목적 범위 준수
- 공식 출처와 원문 URL 표시
- 트래픽 초과 등 제공기관의 제한 정책 준수
- 제3자 권리가 포함된 정보는 별도 조건 확인
- API Key를 코드·DB·로그에 저장하거나 공개하지 않음
- 운영 서비스 전 활용사례 등록 등 승인 절차 재확인

공식 근거:

- 국가법령정보 공동활용 이용안내: https://open.law.go.kr/LSO/information/guide.do
- 공동활용 서비스 안내: https://open.law.go.kr/LSO/information/service.do
- Open API 활용방법: https://open.law.go.kr/LSO/openApi/openApiManual.do
- Open API 활용가이드: https://open.law.go.kr/LSO/openApi/guideList.do

### 9.2 주의

DB 저장 가능 여부와 무제한 호출 가능 여부는 다른 문제다. 공개 안내에서 계정별 상세 호출량은 확인되지 않았으므로 실제 승인 화면의 제한값을 기록하고 이를 수집 설정에 반영한다.

## 10. Open API 호출 방식 확정

사용자 질문마다 Open API를 호출하지 않는다. 사전 수집 후 Local DB를 검색하는 방식을 기본으로 한다.

```text
목록 API
→ external_id 목록
→ 각 ID로 본문 API 호출
→ Raw 응답 선택적 보관
→ 공통 Schema 정규화
→ PostgreSQL Upsert
→ Chunk/Embedding
```

법령은 MVP 핵심 법령부터 수집한다.

- Housing: 주택임대차보호법, 민법
- Labor: 근로기준법, 근로자퇴직급여 보장법
- Consumer: 전자상거래법, 소비자기본법, 민법

판례는 카테고리별 검색어로 목록을 수집한 뒤 본문을 조회한다.

### 10.1 MVP 법률 데이터 범위

모든 생활법률 데이터를 수집하지 않는다. 다음 시연 질문과 직접 관련된 범위부터 적재한다.

| category | 핵심 법령 | 판례 검색어 |
|---|---|---|
| `housing` | 주택임대차보호법, 민법 | 임대차보증금, 보증금 반환, 임대차 종료 |
| `labor` | 근로기준법, 근로자퇴직급여 보장법 | 퇴직금, 임금 체불, 부당해고 |
| `consumer` | 전자상거래법, 소비자기본법, 민법 | 중고거래, 물품 미배송, 환불, 매매대금 |

이번 주 검색 평가는 카테고리별 검증된 Seed 문서 최소 5건과 질문 5개로 시작한다. 데이터 수는 검색 품질과 시연 안정성을 확보하는 범위에서 늘린다.

## 11. 데이터 갱신 방식 확정

```text
external_id 없음
→ INSERT

external_id 있음 + content_hash 동일
→ SKIP

external_id 있음 + content_hash 변경
→ UPDATE
→ 기존 Chunk 교체
→ Embedding 재생성
```

MVP에서는 수동 수집 명령으로 실행한다.

- 개발 데이터 준비 시 1회
- 통합 테스트 전 1회
- 최종 시연 전 1회

운영 확장 시 일 또는 주 단위 스케줄과 법령 변경이력 API를 적용한다.

## 12. Chunking과 검색

법령은 조문 단위로 Chunking한다. 판례는 판시사항, 판결요지, 사실관계, 법원의 판단과 결론 등 의미 단위로 분리한다.

판례의 초기 Chunk 크기는 500~800 token, overlap은 50~100 token을 사용하되 검색 평가 결과에 따라 조정한다.

검색 순서:

```text
category filter
→ document_type filter
→ keyword/exact search
→ vector search
→ score 결합
→ document 단위 중복 제거
→ relevance threshold
→ Top 3
```

초기 Hybrid 가중치는 Vector 0.7, Keyword 0.3으로 시작하되 최적값으로 단정하지 않고 15개 평가 질문 결과로 조정한다.

## 13. MCP 확정 내용

Legal MCP Server 하나를 운영하고 내부 모듈을 역할별로 분리한다.

```text
legal_mcp/
├─ server.py
├─ tools/
├─ services/
├─ repositories/
├─ providers/
├─ infrastructure/
├─ schemas/
└─ core/
```

확정 Tool:

```text
search_laws(query, category, top_k=3)
search_cases(query, category, top_k=3)
get_law_article(law_name, article_number)
```

모든 Tool은 `ToolResult` Envelope를 반환한다. 검색 결과 없음은 오류가 아니라 빈 목록 또는 `null`이다.

## 14. Agent 확정 내용

- `AgentProfile + AgentRegistry + 공통 AgentRuntime`
- 전문 Agent 하나만 선택
- Tool Allowlist는 Backend 코드에서 검증
- Tool Result를 LLM에 전달하고 추가 행동을 재판단
- 최대 4 Step, 최대 3 Tool Call
- MCP 10초, LLM 20초 Timeout
- Evidence에 없는 법률정보 생성 금지
- Trace는 테스트·운영용으로만 사용

상세 내용은 `docs/AI agent 명세서.md`를 따른다.

## 15. Frontend Flow 및 디자인 초안

Frontend는 `docs/회의내용/0903_프론트엔드예시화면.png`를 기준 화면으로 사용한다. 사례 분석을 중심으로 관련 결과를 한 화면에 연결하고, 기능별 메뉴를 왼쪽 사이드바에 배치하는 혼합형 구조로 확정한다.

```text
카테고리 선택
→ 사례 입력
→ 분석하기
→ 내 상황 요약
→ 관련 법령
→ 유사 판례 Top 3
→ 실제 판결 결과
→ 공식 출처
→ 추가 확인 질문
→ 주의사항
→ 저장하기
```

사이드바:

```text
선택한 법률 분야
내 사례 분석
법 검색
실제 사례
쉬운 법률 용어
필요 서류
다음 행동
FAQ
질의 이력
법률 정보 안내
```

메인 결과 영역:

```text
사례 입력 + 분석하기
AI가 정리한 상황 요약 + 핵심 쟁점
관련 법령
유사 판례 Top 3
판결 결과·선고일·유사한 점·유사도
쉬운 법률 용어
필요 서류
다음 행동
FAQ
공식 원문 링크와 법률 정보 안내
```

핵심 MVP는 사례 분석, 관련 법령과 유사 판례 Top 3까지다. 쉬운 법률 용어, 필요 서류, 다음 행동, FAQ와 질의 이력은 같은 디자인 구조를 유지하되 시간이 부족하면 단계적으로 비활성화하거나 후순위 구현한다.

표시 정책:

- 법령 카드에는 법령명·조문·요약·공식 원문 링크를 표시한다.
- 판례 카드에는 법원·사건 식별정보·선고일·판결 결과·유사한 점·score를 표시한다.
- score는 `유사도`로 표시하되 승소 가능성처럼 표현하지 않는다.
- AI 상황 요약은 법적 결론이 아니라 질문과 검색 근거의 정리로 표현한다.
- 모든 화면에 법률 자문과 승패 예측을 제공하지 않는다는 안내를 표시한다.
- 예시 화면의 사건번호와 내용은 디자인용이므로 실제 서비스에서는 MCP가 반환한 검증된 데이터만 표시한다.

Food MCP Smoke Test UI는 개발 모드에서만 노출한다.

## 16. Mock 검색 테스트 계획

Mock은 허위 법률정보가 아니라 공식 출처를 확인한 고정 Seed 데이터다.

```text
housing 5개 질문
labor 5개 질문
consumer 5개 질문
총 15개 질문
```

통과 기준:

- 최소 12개 질문에서 기대 문서가 Top 3 안에 포함
- 모든 결과에 공식 Source URL 포함
- category와 document_type 필터 준수
- 동일 문서 Chunk 중복 제거
- 낮은 관련성은 빈 결과
- 결과 최대 3개, score 내림차순

테스트는 이번 주에 실행하며 자동화 결과와 평가 데이터를 `tests/evaluation`에서 관리한다.

## 17. 개발 순서

1. Team Contract v1 팀 승인
2. LaborAgent 하나와 결정적인 Mock Tool로 Agent Loop 검증
3. DB Migration과 공식 출처가 있는 Seed 데이터 준비
4. Chunking, Embedding과 pgvector 검색
5. `search_cases` 실제 검색 E2E
6. `search_laws`, `get_law_article`
7. 검증된 Runtime을 HousingAgent와 ConsumerAgent로 확장
8. Backend 응답 계약 교체
9. Frontend 실제 결과 연결
10. Redis 임시 상태와 저장하기
11. 15개 Mock RAG 평가
12. 대표 질문 3개 전체 E2E

첫 번째 통합 목표는 다음 한 경로다.

```text
퇴직금 질문
→ LaborAgent
→ search_cases
→ Legal MCP
→ pgvector
→ 공식 판례 Top 3
→ Agent 답변
→ Frontend 표시
```

## 18. 테스트와 완료 기준

- 3개 카테고리와 Agent
- LLM Tool 선택과 재판단
- Legal MCP Tool 3개
- PostgreSQL + pgvector 실제 검색
- 공식 법령과 판례 또는 검증된 Seed
- 법령·판례 Top 3
- 판결 결과와 공식 출처
- no-evidence 처리
- 법률 안전 정책
- 사용자 명시적 저장
- 대표 질문 3개 E2E
- Agent 정상·예외·안전성 테스트
- RAG 15개 검색 평가
- README 실행 절차

## 19. 현재 구현 상태

현재 저장소는 Frontend → Backend → Mock HTTP Legal MCP 연결 Skeleton 단계다. 2026-09-04 기준 기존 테스트 6개가 통과했다.

아직 구현되지 않은 핵심 항목:

- 실제 AgentProfile/Registry/Runtime
- 실제 Legal MCP 프로토콜 Tool
- DB Repository와 RAG
- Open API 수집·정규화·갱신
- Redis Registry와 사용자 저장 API
- Agent 및 RAG 평가 테스트

문서 확정과 구현 완료를 혼동하지 않는다.

## 20. 일정과 작업 방식

### 09.04 오늘

- 최종 계획, DB/Open API/Agent 계약 문서화
- 팀원에게 추천 확정안과 미정 사항 공유
- 예시 화면을 기준으로 Frontend Flow와 디자인 구조 확정

### 주말

- 상옥: 추천 Flow를 실제 Streamlit 화면에 연결할 준비
- 다혁: LaborAgent + Mock Tool Runtime 구현 준비
- 병훈: ToolResult와 Legal MCP Tool Skeleton 준비
- 지혜: Migration, 검증된 Seed, 수집·Embedding 스크립트 준비

### 월요일

- DB → MCP → Agent → Backend → Frontend 첫 통합
- 퇴직금 대표 질문 하나를 먼저 끝까지 연결
- 첫 경로가 성공한 뒤 나머지 category와 부가 기능 확장

핵심 경로가 완료되기 전에는 FAQ, 관리자, SSE와 복잡한 로그인 구현을 시작하지 않는다.

## 21. 팀 확인이 남은 항목

- 본 문서의 DB Schema와 ID 추천 확정안 승인
- 승인 계정의 Open API 상세 호출 제한
- 익명 사용자 + 저장하기 방식을 적용할지, 간단 로그인까지 포함할지

위 항목은 핵심 검색 E2E를 막지 않는 범위에서 후속 결정한다. Open API 호출 제한은 수집 실행 전에 승인 계정 화면에서 확인한다.
