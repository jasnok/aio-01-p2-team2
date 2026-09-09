# 2026-09-06 DB·RAG·Redis 대화 요약

> 대화일: 2026-09-06 일요일  
> 프로젝트: 생활 법률 검색 AI Agent  
> 범위: 주택임대차·노동·소비자/중고거래  
> 목적: 3일 미니프로젝트를 위한 데이터·DB·RAG·Redis 사전 준비 방향 확정

## 1. 프로젝트 전제

사용자가 다음 세 분야의 생활 법률 질문을 입력하면, 관련 법령과 판례·공식 사례를 검색해 근거와 함께 설명하는 서비스를 준비한다.

```text
housing  → 주택임대차·보증금
labor    → 퇴직금·임금체불·부당해고
consumer → 중고거래·미배송·환불·사기
```

대표 질문:

1. 계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다.
2. 퇴직했는데 퇴직금을 받지 못했습니다.
3. 중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다.

3일 단기 프로젝트이지만 DB·RAG·Redis 기반이 준비돼야 다른 팀원이 Backend, MCP, Agent, Frontend 작업을 진행할 수 있다는 점을 전제로 논의했다.

---

## 2. 데이터 운영 방향

최종 방향은 **파일 데이터 우선, 부족한 현행 법령·판례 본문은 외부 API로 사전 수집**이다.

```text
공공 파일 데이터
+ 부족한 공식 법령·판례 API 데이터
→ 원본 보관
→ 정규화
→ PostgreSQL 저장
→ Chunk 생성
→ Embedding
→ pgvector 저장
```

사용자 질문이 들어올 때 외부 API를 실시간 호출하는 방식은 기본 흐름으로 사용하지 않는다.

```text
사용자 질문
→ 질문 Embedding 생성
→ 내부 PostgreSQL + pgvector 검색
→ 공식 근거 반환
```

외부 API는 다음 시점에 사용한다.

- 최초 데이터 준비
- 통합 테스트 전 데이터 보충
- 최종 시연 전 데이터 갱신
- 법령·판례의 최신 본문 또는 파일에 없는 상세본문 확보

즉, API 응답도 수집한 다음 정규화하여 DB와 pgvector에 미리 넣는다.

---

## 3. 필요한 법령과 사례 범위

### 3.1 Housing

핵심 법령:

- 주택임대차보호법
- 주택임대차보호법 시행령
- 민법의 임대차, 채무불이행, 계약 해지·해제 관련 조문

판례 검색 범위:

- 임대차보증금
- 보증금 반환
- 전세보증금
- 임대차 종료
- 대항력
- 우선변제권
- 임차권등기명령

### 3.2 Labor

핵심 법령:

- 근로기준법
- 근로자퇴직급여 보장법
- 필요 시 최저임금법

판례·판정례 검색 범위:

- 퇴직금
- 임금 체불
- 부당해고
- 해고 통보
- 근로계약
- 평균임금
- 근로자성

### 3.3 Consumer

핵심 법령:

- 민법의 매매, 채무불이행, 계약 해제 관련 조문
- 형법 제347조 사기
- 소비자기본법
- 전자상거래 등에서의 소비자보호에 관한 법률

판례·사례 검색 범위:

- 중고거래
- 물품 미배송
- 환불
- 사기
- 매매대금
- 계약 해제

개인 간 중고거래에 전자상거래법이 항상 적용되는 것은 아니므로 민법과 형법 근거를 함께 검색해야 한다.

---

## 4. 공공데이터포털 파일 검토

### 4.1 소비자 피해구제 데이터

처음 찾으려던 `한국소비자원_소비자 피해구제 정보`는 검색되지 않았다. 대체 자료로 다음 파일을 확인했다.

```text
한국소비자원_품목별 피해구제 사례_20220331.xml
```

확인 내용:

- XML 파일
- 총 678개 사례
- 주요 필드: 일련번호, 품목, 출처, 제목, 질문, 답변
- 소비자·중고거래 분야의 질문·답변형 RAG 자료로 활용 가능
- 일반 XML이 아니라 Excel SpreadsheetML 형식이므로 네임스페이스를 처리하는 파서가 필요
- 답변 당시의 법령·판례 기준일 수 있으므로 현행 법령과 함께 사용
- 법원 판례가 아니므로 `CONSULTATION` 유형으로 관리하는 것이 적절

### 4.2 중앙노동위원회 주요판정사례

```text
고용노동부 중앙노동위원회_주요판정사례_20260506.csv
```

확인 내용:

- CP949 CSV
- 약 399건
- 제목, 위원회명, 작성일자 중심
- 판정서 전체본문이 없는 색인 자료
- 법원 판례와 구분하여 `ADMIN_DECISION`으로 관리
- 상세본문을 확보한 건만 직접적인 RAG 근거로 사용하는 것이 적절

### 4.3 고용노동 관련 법령 내용

```text
고용노동부_고용노동관련 법령 내용_20260715.csv
```

확인 내용:

- CP949 CSV
- 약 6,000건
- 필드: 번호, 법령명, 조문명
- 조문 본문이 없으므로 현행 법령 RAG 원문으로는 부족
- 대상 법령·조문을 찾는 색인으로 사용
- 실제 조문 본문은 국가법령정보 공동활용에서 보충

### 4.4 법제처 공포법령 조단위

```text
법제처_국가법령정보센터_공포법령조단위_20140814.csv
```

확인 내용:

- UTF-8 BOM CSV
- 약 16,759건
- 조문 식별정보 중심
- 법령명과 조문 본문이 부족
- 2014년 자료이므로 현행 법령 근거로 직접 사용하기 어려움
- 파이프라인 시험 또는 식별자 참고용

### 4.5 법제처 일상용어

```text
법제처_일상용어_20230825.csv
```

확인 내용:

- CP949 CSV
- 약 81,970건
- 어려운 법률용어를 쉬운 표현으로 보여주거나 질의를 확장하는 용도
- 법적 답변의 직접 근거로 사용하지 않음

---

## 5. 파일별 인코딩

| 파일 | 인코딩 |
|---|---|
| 소비자원 피해구제 XML | UTF-8 |
| 중앙노동위원회 CSV | CP949 |
| 고용노동 법령 CSV | CP949 |
| 법제처 공포법령 CSV | UTF-8 BOM |
| 법제처 일상용어 CSV | CP949 |

파일마다 인코딩이 다르므로 `source_manifest.json`에 원본 형식과 인코딩을 기록해야 한다.

---

## 6. 파일 데이터와 외부 API의 역할

| 자료 | 확보 방식 | 최종 사용 |
|---|---|---|
| 소비자 피해구제 사례 | 보유 XML 파일 | PostgreSQL + pgvector |
| 법제처 일상용어 | 보유 CSV 파일 | 질의 확장·쉬운 용어 표시 |
| 노동위원회 사례 제목·메타데이터 | 보유 CSV 파일 | 상세본문 수집대상 색인 |
| 고용노동 법령 목록 | 보유 CSV 파일 | 현행 법령 수집대상 색인 |
| 현행 법령 조문 본문 | 국가법령정보 공동활용 API | PostgreSQL + pgvector |
| 법원 판례 상세본문 | 국가법령정보 공동활용 API 등 공식 출처 | PostgreSQL + pgvector |
| Housing 데이터 | 확보된 전용 파일이 없으므로 API 및 공식 Seed | PostgreSQL + pgvector |

파일에 본문이 없으면 제목이나 메타데이터를 임의로 늘려 법적 근거처럼 만들지 않는다.

---

## 7. JSON과 JSONL의 차이

### JSON

하나의 JSON 문서에 배열이나 객체 전체를 저장한다.

```json
{
  "documents": [
    {"id": "1", "title": "문서1"},
    {"id": "2", "title": "문서2"}
  ]
}
```

설정과 데이터 계약에 적합하다.

```text
source_manifest.json
keywords.json
document.schema.json
```

### JSONL

한 줄에 독립된 JSON 객체 하나를 저장한다.

```jsonl
{"id":"1","title":"문서1"}
{"id":"2","title":"문서2"}
```

대용량 문서 처리, 중간 재시작, 한 줄 단위 스트리밍에 적합하다.

```text
documents.jsonl
chunks.jsonl
questions.jsonl
```

---

## 8. 권장 데이터 디렉토리 구조

```text
database/
├─ README.md
├─ .env.example
├─ requirements.txt
├─ sources/
│  ├─ source_manifest.json
│  └─ keywords.json
├─ schemas/
│  ├─ document.schema.json
│  └─ chunk.schema.json
├─ raw/
│  ├─ files/
│  │  ├─ housing/
│  │  ├─ labor/
│  │  ├─ consumer/
│  │  ├─ laws/
│  │  ├─ cases/
│  │  └─ terminology/
│  └─ api/
│     ├─ laws/
│     └─ cases/
├─ normalized/
│  ├─ documents.jsonl
│  └─ chunks.jsonl
├─ migrations/
│  ├─ 001_init.sql
│  ├─ 002_search_indexes.sql
│  └─ 003_saved_conversations.sql
├─ scripts/
│  ├─ setup_database.ps1
│  ├─ migrate.py
│  ├─ build_rag.py
│  ├─ normalize_files.py
│  ├─ collect_laws.py
│  ├─ collect_cases.py
│  ├─ build_chunks.py
│  ├─ create_embeddings.py
│  ├─ load_postgres.py
│  └─ verify_database.py
├─ evaluation/
│  ├─ questions.jsonl
│  └─ expected_sources.jsonl
└─ tests/
   ├─ test_normalize.py
   └─ test_retrieval.py
```

---

## 9. 데이터 계약

모든 파일과 API 응답은 `NormalizedLegalDocument` 공통 구조로 변환한다.

핵심 필드:

```text
external_id
document_type
category
title
summary
content
law_name
article_number
case_number
case_name
court
decided_at
judgment_result
source_name
source_url
source_type
raw_file
effective_date
source_updated_at
content_hash
metadata
```

문서 유형:

```text
LAW
CASE
GUIDELINE
ADMIN_DECISION
CONSULTATION
```

카테고리:

```text
housing
labor
consumer
```

중복 및 갱신 기준:

```text
UNIQUE(source_name, external_id)
```

```text
external_id 없음
→ INSERT

external_id 있음 + content_hash 동일
→ SKIP

external_id 있음 + content_hash 변경
→ UPDATE
→ 기존 Chunk 교체
→ 재임베딩
```

---

## 10. PostgreSQL과 pgvector

SQL은 법령·판례를 직접 하나씩 작성하는 용도가 아니라 데이터 저장 구조와 검색 인덱스를 만드는 용도다.

필요한 테이블:

```text
legal_documents
legal_chunks
ingestion_runs
users
saved_conversations
saved_messages
saved_message_sources
```

주요 조건:

- `legal_documents.id`: `BIGSERIAL`
- 외부 식별: `UNIQUE(source_name, external_id)`
- 변경 감지: `content_hash`
- 문서와 Chunk: FK + `ON DELETE CASCADE`
- Embedding: `VECTOR(1536)`
- Vector 검색: cosine HNSW 인덱스
- Keyword 검색: 제목·요약·본문 GIN 인덱스

사용자가 `저장하기`를 눌렀을 때만 질문·답변·근거를 PostgreSQL에 장기 저장한다.

---

## 11. OpenAI Embedding

Embedding 모델은 다음으로 확정했다.

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

DB 문서 적재 시 사용하는 모델과 MCP가 사용자 질문을 Embedding할 때 사용하는 모델·차원은 같아야 한다.

모델을 나중에 변경할 수 있지만 다음 작업이 필요하다.

- 환경설정 변경
- Embedding 버전 변경
- pgvector 컬럼 차원이 달라지면 Migration
- 기존 Chunk 전체 재임베딩

---

## 12. Chunking 기준

```text
법령
→ 조문 단위

판례
→ 판시사항, 판결요지, 사실관계, 법원의 판단, 결론

소비자 피해구제 사례
→ 제목 + 품목 + 질문 + 답변
```

판례 초기 권장값:

```text
chunk size: 500~800 token
overlap: 50~100 token
```

Embedding 벡터 1,536개를 JSONL에 저장하면 파일이 지나치게 커질 수 있으므로, Chunk 내용과 메타데이터는 JSONL에 두고 벡터는 생성 즉시 PostgreSQL에 저장하는 방법을 권장했다.

---

## 13. Redis와 Cache

Redis에는 법령·판례와 Embedding 원본을 사전 적재하지 않는다.

Redis 용도:

- 최근 대화 문맥
- 검색 결과 Cache
- 요청 상태
- Agent Tool 실행 상태

확정한 최근 대화 정책:

```env
CONVERSATION_TTL_SECONDS=86400
CONVERSATION_MAX_MESSAGES=20
```

최근 대화 예시:

```text
Key: conversation:{session_id}
자료구조: List
처리: RPUSH → LTRIM -20 -1 → EXPIRE 86400
```

검색 Cache 예시:

```text
Key: legal-search:v1:{category}:{document_type}:{query_hash}:{top_k}
자료구조: String(JSON)
권장 TTL: 600초
```

Redis 장애 시 최근 문맥과 Cache만 제한하고 PostgreSQL·pgvector 검색은 계속 동작해야 한다.

---

## 14. Docker Compose 논의

프로젝트 기준 파일은 `docker-compose_v2.yml`로 정했다.

필요 서비스:

```text
PostgreSQL 16 + pgvector
Redis 7
```

역할:

```text
docker compose up
→ 빈 PostgreSQL과 Redis 서버 실행

Migration 실행
→ PostgreSQL 테이블과 인덱스 생성

build_rag 실행
→ 법령·판례·Chunk·Embedding 적재

Backend 실행
→ Redis 최근 대화 저장

MCP 검색 실행
→ Redis 검색 Cache 저장
```

Docker 실행만으로 데이터가 자동 주입되는 것은 아니다.

Migration 디렉토리를 `/docker-entrypoint-initdb.d`에 연결하면 빈 PostgreSQL 볼륨 최초 생성 시 SQL이 자동 실행되지만, 이미 초기화된 볼륨에는 재적용되지 않는다. 기존 DB를 유지하려면 별도의 `migrate.py` 방식이 더 안전하다.

---

## 15. 필요한 실행 파일

팀원이 직접 실행하는 진입점은 다음 네 파일로 단순화한다.

```text
setup_database.ps1
migrate.py
build_rag.py
verify_database.py
```

### `setup_database.ps1`

```text
Docker PostgreSQL·Redis 실행
→ Python 패키지 확인
→ Migration
→ RAG 데이터 구축
→ 최종 검증
```

### `migrate.py`

```text
schema_migrations 확인
→ 아직 적용되지 않은 SQL만 이름순 실행
→ 적용 이력 기록
```

### `build_rag.py`

```text
Manifest 검증
→ 파일/API 원본 정규화
→ Schema 검증
→ Chunk 생성
→ 문서 Upsert
→ OpenAI Embedding
→ pgvector 저장
→ ingestion_runs 기록
```

### `verify_database.py`

```text
PostgreSQL 연결
Redis 연결
vector 확장
필수 테이블·인덱스
카테고리별 문서 수
공식 source_url
Embedding 누락
Embedding 1536차원
Redis 20개 제한과 TTL
```

권장 실행 순서:

```powershell
docker compose --env-file .env -f docker-compose_v2.yml up -d
python database/scripts/migrate.py
python database/scripts/build_rag.py
python database/scripts/verify_database.py
```

---

## 16. 환경변수와 비밀번호

`.env.example`은 Git에 올릴 수 있지만 실제 비밀번호와 API Key를 넣으면 안 된다.

```text
.env.example
→ 변수명과 예시 형식
→ Git 포함 가능

.env
→ 실제 비밀번호와 API Key
→ Git 제외
```

OpenAI Key, PostgreSQL 비밀번호, Redis 비밀번호는 실제 `.env` 또는 실행 환경에서만 관리한다.

Redis 비밀번호가 필요해진 이유는 `docker-compose_v2.yml`에서 `requirepass`를 사용하도록 설정했기 때문이다. 기존 Redis가 비밀번호 없이 로컬에서만 사용됐다면 반드시 추가해야 하는 것은 아니지만, 다른 팀원 PC에서 네트워크로 접근한다면 비밀번호 사용을 권장한다.

인증 정책은 먼저 팀에서 합의해야 한다.

---

## 17. Mock과 공식 Seed 구분

```text
Frontend Mock Fixture
→ 화면과 API 계약 테스트
→ 실제 법률 DB와 pgvector에 넣지 않음
→ is_mock=true 표시
```

```text
공식 출처를 확인한 고정 Seed
→ RAG E2E와 검색평가용
→ PostgreSQL과 pgvector에 실제 적재
→ 공식 source_url 필수
```

`Mock 데이터 사전주입`이라는 표현은 오해할 수 있으므로, DB에 넣는 데이터는 `공식 검증 Seed`라고 부르는 것이 적절하다.

3일 MVP 권장 범위:

- 카테고리별 공식 검증 Seed 최소 5건
- 카테고리별 평가 질문 5개
- 총 15개 질문 중 최소 12개에서 기대 문서가 Top 3에 포함

---

## 18. 2026-09-06 당시 저장소 점검 결과

확인된 구조:

```text
database/migrations/001_init.sql
database/raw/files/consumer/
database/raw/files/labor/
database/raw/files/laws/
database/raw/files/terminology/
database/scripts/.gitkeep
database/seeds/.gitkeep
database/.env.example
database/requirements.txt
```

당시 부족했던 항목:

- `sources/source_manifest.json`
- `sources/keywords.json`
- `schemas/`
- `raw/api/`
- `normalized/`
- `evaluation/`
- `tests/`
- 수집·정규화·Chunk·Embedding·적재 스크립트
- Housing 전용 원본
- 현행 법령 본문
- 법원 판례 상세본문
- 공식 검증 Seed
- Redis 최근 대화 구현
- Redis 검색 Cache 구현

당시 `001_init.sql`에는 pgvector와 기본 문서·Chunk 구조는 있었지만 최종 계획의 필드와 테이블이 모두 반영된 상태는 아니었다.

---

## 19. 최종 합의된 작업 우선순위

### 1단계: 데이터 계약

- `source_manifest.json`
- `keywords.json`
- 문서와 Chunk Schema
- 문서유형·카테고리·ID·출처 정책

### 2단계: DB

- 최종 `001_init.sql`
- 검색 인덱스
- Migration 실행 방식
- `external_id + content_hash` Upsert

### 3단계: 최소 실제 데이터

- 소비자원 XML 정규화
- 현행 핵심 법령 조문
- 카테고리별 검증된 판례 또는 공식 Seed 최소 5건

### 4단계: RAG

- Chunk 생성
- `text-embedding-3-small`
- pgvector 적재
- Keyword + Vector Hybrid Search

### 5단계: Redis

- 최근 대화 24시간·최대 20개
- 검색 Cache
- Redis 장애 시 DB 검색 유지

### 6단계: 검증

- 대표 질문 3개 E2E
- 평가 질문 15개
- Top-3 적중 12개 이상
- 공식 출처 URL 확인

---

## 20. 완료 상태의 정의

다음 파일이 존재하는 것만으로 사전준비가 완료되는 것은 아니다.

```text
SQL
Docker Compose
Raw CSV/XML
.env.example
```

다음 결과를 실제로 확인해야 완료다.

```text
Migration 성공
→ legal_documents에 공식 문서 존재
→ legal_chunks에 Chunk 존재
→ embedding 차원 1536
→ MCP 검색 Top 3 반환
→ 같은 검색의 Redis Cache hit
→ Backend 최근 대화 List 최대 20개
→ TTL 약 86400초
```

최소 통합 성공 경로:

```text
퇴직금 질문용 공식 법령·판례 Seed
→ PostgreSQL 적재
→ Chunk
→ OpenAI Embedding
→ pgvector
→ MCP search_cases
→ Redis Cache
→ Backend 응답
```

## 21. 한 문장 요약

2026년 9월 6일 논의의 결론은 **공공 파일을 우선 사용하고 부족한 현행 법령·판례 본문은 외부 API로 미리 수집한 뒤, 모든 공식 근거를 PostgreSQL과 pgvector에 사전 적재하며, Redis는 최근 대화와 검색 Cache에만 사용하는 재현 가능한 데이터 준비 파이프라인을 구축한다**는 것이다.
