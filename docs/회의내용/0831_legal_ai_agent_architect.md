# 법률 AI Agent 설계 가이드

## 1. 프로젝트 개요

법률 관련 AI Agent를 만들 때는 단순히 LLM 하나에 법률 질문을 전달하는 구조보다 다음 요소를 분리하여 설계하는 것이 좋다.

- LLM
- AI Agent
- RAG
- MCP Server
- Tool
- PostgreSQL + pgvector
- Backend API
- Frontend

전체 구조:

```text
사용자
  ↓
Frontend
  ↓
Backend API
  ↓
Legal AI Agent
  ↓
LLM ────────────────┐
  │                  │
  │ Tool 선택         │ 답변 생성
  ↓                  │
MCP Server           │
  ├─ 법령 검색 Tool   │
  ├─ 판례 검색 Tool   │
  ├─ 문서 검색 Tool   │
  └─ 조문 조회 Tool   │
        ↓             │
   RAG / Retrieval    │
        ↓             │
PostgreSQL + pgvector │
        ↓             │
법률 근거 자료 ────────┘
        ↓
근거 포함 최종 답변
```

핵심은 LLM에게 법률 지식을 기억해서 답하게 하지 않고, 실제 법률 자료를 먼저 검색하게 만드는 것이다.

## 2. Agent 역할 범위

처음부터 모든 법률 분야를 다루기보다 특정 분야로 시작하는 것이 좋다.

예시:
- 근로기준법
- 임대차
- 소비자 분쟁
- 개인정보
- 계약 관련 기본 법률 정보

예시 흐름:

```text
사용자 질문
   ↓
질문 의도 분석
   ↓
관련 법령 검색 필요
   ↓
search_laws Tool
   ↓
관련 조문 검색
   ↓
필요하면 판례 검색
   ↓
검색된 근거를 LLM에 전달
   ↓
근거를 인용한 답변
```

## 3. 법률 데이터 구조

```text
laws
├─ 법령명
├─ 조문 번호
├─ 조문 제목
├─ 조문 내용
├─ 시행일
├─ 출처
└─ embedding

cases
├─ 사건번호
├─ 법원
├─ 선고일
├─ 사건명
├─ 판결 요지
├─ 판결 내용
├─ 출처
└─ embedding
```

PostgreSQL + pgvector 예시:

```sql
CREATE TABLE legal_documents (
    id BIGSERIAL PRIMARY KEY,
    document_type VARCHAR(30) NOT NULL,
    title TEXT NOT NULL,
    article_number VARCHAR(50),
    content TEXT NOT NULL,
    source TEXT,
    effective_date DATE,
    embedding vector(1536)
);
```

`document_type` 예시:

```text
LAW
CASE
REGULATION
GUIDELINE
```

## 4. RAG 동작 방식

```text
사용자 질문
   ↓
Embedding Model
   ↓
질문 Vector 생성
   ↓
pgvector 유사도 검색
   ↓
관련 법령/판례 검색
   ↓
검색 결과를 LLM에 전달
   ↓
근거 기반 답변 생성
```

검색 SQL 예시:

```sql
SELECT
    id,
    title,
    article_number,
    content,
    source,
    1 - (embedding <=> %s::vector) AS similarity
FROM legal_documents
ORDER BY embedding <=> %s::vector
LIMIT 5;
```

## 5. MCP Server 역할

추천 Tool:

```text
search_laws
→ 관련 법령 검색

get_law_article
→ 특정 법령/조문 원문 조회

search_cases
→ 관련 판례 검색

get_case_detail
→ 특정 판례 상세 조회

search_legal_documents
→ 벡터 기반 통합 검색
```

예시:

```python
@mcp.tool()
def search_laws(query: str, limit: int = 5) -> dict:
    """질문과 관련된 법령 및 조문을 검색합니다."""
```

## 6. Agent와 RAG 차이

```text
RAG
= 자료를 찾는 방법

Agent
= 어떤 자료를 언제 찾아야 하는지 판단하는 주체
```

Agent 예시:

```text
질문
 ↓
LLM 판단
 ↓
법령 검색만 필요한가?
 ├─ YES → search_laws
 └─ NO
      ↓
   판례도 필요한가?
      ↓
   search_cases
      ↓
   상세 조문이 필요한가?
      ↓
   get_law_article
```

## 7. LLM 역할

LLM은 자연어 이해, Tool 선택 판단 지원, 최종 답변 생성을 담당한다.

권장 Instructions:

```text
당신은 법률 정보 검색 Agent입니다.

반드시 Tool을 통해 제공된 법률 자료만 근거로 답변하세요.

근거가 부족하면 추측하지 말고
"확인 가능한 자료가 부족합니다."라고 답하세요.

법률명, 조문 또는 판례를 답변에 표시하세요.

개별 사건의 결과를 확정적으로 단정하지 마세요.
```

## 8. 출처와 근거 표시

권장 답변 구조:

```text
결론

관련 법령

관련 판례

관련 근거

출처

주의사항
```

즉:

```text
답변
+
근거
+
출처
+
불확실성 / 주의사항
```

을 한 세트로 제공한다.

## 9. 권장 Workflow

```text
START
 ↓
사용자 질문
 ↓
법률 질문인가?
 ↓
질문 유형 분류
 ↓
Agent
 ↓
필요 Tool 선택
 ↓
법령/판례 검색
 ↓
관련 자료 충분?
 ├─ NO → 추가 검색
 └─ YES
      ↓
근거 정리
 ↓
LLM 답변 생성
 ↓
Citation 검증
 ↓
최종 답변
```

## 10. 권장 프로젝트 구조

```text
legal_ai/
│
├── frontend/
│   └── app.py
│
├── backend/
│   ├── main.py
│   ├── routers/
│   │   └── legal_router.py
│   └── schemas/
│       └── legal.py
│
├── legal_mcp/
│   ├── server.py
│   ├── tools/
│   │   ├── law_tools.py
│   │   └── case_tools.py
│   ├── services/
│   │   ├── law_service.py
│   │   └── case_service.py
│   ├── repositories/
│   │   ├── law_repository.py
│   │   └── case_repository.py
│   ├── providers/
│   │   └── embedding.py
│   ├── infrastructure/
│   │   └── database.py
│   └── schemas/
│       ├── law.py
│       └── case.py
│
├── agent/
│   ├── legal_agent.py
│   └── instructions.py
│
├── database/
│   ├── create_tables.sql
│   └── populate_embeddings.py
│
└── tests/
```

핵심 계층 흐름:

```text
server
 ↓
tools
 ↓
services
 ↓
repositories
 ↓
database
```

## 11. 실제 요청 처리 예시

사용자 질문:

```text
월세 계약이 끝났는데 집주인이 보증금을 안 돌려줘. 어떻게 해야 해?
```

처리 흐름:

```text
Frontend
 ↓
Backend
 ↓
Legal Agent
 ↓
search_laws
 ↓
pgvector
 ↓
관련 법령 검색
 ↓
필요하면 search_cases
 ↓
관련 판례 검색
 ↓
LLM
 ↓
근거 기반 최종 답변
```

## 12. pgvector와 일반 SQL 역할 구분

정확한 법령/조문 요청:

```text
근로기준법 제36조 알려줘
```

→ SQL / Keyword Search

```sql
WHERE law_name = '근로기준법'
AND article_number = '36'
```

자연어 의미 질문:

```text
회사가 월급을 계속 늦게 주는데 관련 법이 뭐야?
```

→ Vector Search

복합적인 법률 질문:

```text
SQL + Vector + Agent
```

따라서 Hybrid Search 구조를 권장한다.

## 13. MVP 권장 범위

초기 버전:

```text
법률 분야:
근로기준법 관련 질문

DB:
법령/조문 100~500개

MCP Tool:
search_laws
get_law_article

RAG:
PostgreSQL + pgvector

Agent:
Tool 선택 + 근거 기반 답변 생성

Frontend:
질문 입력
답변
관련 법령
출처
```

## 14. 이후 확장 방향

```text
판례 데이터 추가
 ↓
search_cases

노동위원회 자료 추가
 ↓
search_guidelines

문서 업로드
 ↓
PDF RAG

여러 Agent
 ↓
법령 Agent
판례 Agent
문서 분석 Agent
```

## 15. 권장 개발 순서

```text
1. PostgreSQL + pgvector
2. 법령 데이터 수집
3. Chunking + Embedding
4. search_laws MCP Tool
5. get_law_article MCP Tool
6. Legal Agent + LLM
7. FastAPI Backend
8. Streamlit Frontend
9. Citation / Hallucination 검증
10. 판례 RAG 추가
```

## 16. 핵심 개념 정리

| 구성요소 | 역할 |
|---|---|
| Frontend | 사용자 질문 입력과 결과 표시 |
| Backend | API 요청 및 전체 서비스 흐름 관리 |
| LLM | 자연어 이해, 추론, 답변 생성 |
| AI Agent | 필요한 Tool 선택 및 실행 판단 |
| MCP Server | 법률 Tool과 외부 기능 제공 |
| Tool | 법령, 판례, 문서 실제 검색 |
| RAG | 검색된 법률 자료를 LLM에 제공 |
| PostgreSQL | 법률 원문 및 메타데이터 저장 |
| pgvector | 자연어 의미 기반 유사도 검색 |
| Embedding Model | 문서와 질문을 Vector로 변환 |
| Workflow | 전체 처리 단계 및 분기 관리 |

## 17. 최종 방향

초기 목표는 다음과 같이 잡는 것이 좋다.

```text
X
모든 법률 문제를 판단하는 AI 변호사

O
공식 법률 근거를 검색하고
사용자가 이해할 수 있도록 설명하는 AI Agent
```

법률 분야에서는 Agent가 결론을 임의로 생성하는 것보다 공식 자료를 정확하게 찾고 다음 내용을 구분해서 보여주는 구조가 중요하다.

```text
어떤 내용이 검색된 법률 근거인지
어떤 내용이 일반적인 설명인지
어떤 부분은 추가 확인이 필요한지
```

최종 권장 구조:

```text
사용자
 ↓
Frontend
 ↓
Backend
 ↓
Legal Agent + LLM
 ↓
MCP Server
 ↓
Law / Case Tools
 ↓
RAG
 ↓
PostgreSQL + pgvector
 ↓
공식 법률 근거
 ↓
LLM
 ↓
근거 + 출처 + 주의사항을 포함한 최종 답변
```
