# 법률 사례 검색 AI Agent --- MCP Server / Tool 구축 계획

## 1. 전체 방향

DB가 이미 구현됐다는 전제에서 MCP Server는 **DB/RAG 검색 기능을 Agent가
사용할 수 있는 Tool로 포장하는 계층**으로 구성한다.

``` text
사용자
  ↓
Frontend
  ↓
Backend
  ↓
HousingAgent / LaborAgent / ConsumerAgent
  ↓
MCP Client
  ↓
Legal MCP Server
  ↓
Tool
  ├─ search_legal_documents
  ├─ search_cases
  ├─ get_case_detail
  └─ get_law_article
  ↓
Repository / Search Service
  ↓
PostgreSQL + pgvector
  ├─ legal_documents
  └─ legal_chunks
```

핵심 원칙은 다음과 같다.

``` text
MCP = 실제 검색 담당
Agent = 어떤 검색을 할지 판단
```

Backend와 Agent는 DB에 직접 접근하지 않고 MCP Tool을 통해서만 법률
데이터와 판례를 검색한다.

------------------------------------------------------------------------

## 2. MCP 디렉터리 구조

기존 계획의 구조는 다음과 같다.

``` text
legal_mcp/
├─ _ollama_pgvector.py
├─ mcp_server.py
├─ mcp_server1.py
├─ mcp_server2.py
└─ mcp_server3.py
```

하지만 개발 기간이 짧은 MVP 단계에서는 서버를 처음부터 세 개로
분리하기보다 Legal MCP Server 하나를 먼저 구현하는 것을 권장한다.

``` text
legal_mcp/
│
├─ server.py
│
├─ tools/
│  ├─ search_tools.py
│  ├─ case_tools.py
│  └─ law_tools.py
│
├─ services/
│  └─ legal_search_service.py
│
├─ repositories/
│  └─ legal_repository.py
│
├─ providers/
│  └─ embedding.py
│
├─ infrastructure/
│  └─ database.py
│
├─ schemas/
│  └─ legal.py
│
└─ core/
   └─ config.py
```

개념적으로는 다음과 같다.

``` text
MCP Server
 ↓
Tool
 ↓
Service
 ↓
Repository
 ↓
DB
```

`@mcp.tool()` 안에서 SQL, Embedding, 결과 가공을 전부 하지 않고 MCP
Tool을 얇게 유지한다.

``` python
@mcp.tool()
def search_cases(...):
    return service.search_cases(...)
```

------------------------------------------------------------------------

## 3. Database 연결

PostgreSQL 연결 담당 예시는 다음과 같다.

``` python
# legal_mcp/infrastructure/database.py

import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/legal_db"
)

def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )
```

MVP에서는 단순한 Connection 방식으로 시작하고, 실제 서비스 규모가 커지면
Connection Pool 방식으로 확장한다.

------------------------------------------------------------------------

## 4. Embedding 담당

사용자의 자연어 사례를 pgvector에서 검색하려면 MCP에서도 질문을 Vector로
바꿔야 한다.

``` text
사용자 query

"퇴직금을 못 받았습니다."

        ↓

Ollama Embedding

        ↓

[0.12, -0.32, ...]

        ↓

pgvector
```

예:

``` python
# legal_mcp/providers/embedding.py

import requests

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"

def create_embedding(text: str) -> list[float]:

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": text
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    return data["embeddings"][0]
```

중요한 것은 DB에 저장할 때 사용한 Embedding Model과 검색할 때 사용하는
모델이 같아야 한다는 것이다.

------------------------------------------------------------------------

## 5. Repository가 실제 SQL 담당

``` python
# legal_mcp/repositories/legal_repository.py

from legal_mcp.infrastructure.database import get_connection

class LegalRepository:

    def search_cases(
        self,
        embedding: list[float],
        category: str,
        limit: int = 3,
    ):

        sql = """
        SELECT
            d.id AS document_id,
            d.case_number,
            d.case_name,
            d.court,
            d.decided_at,
            d.judgment_result,
            d.summary,
            d.source_name,
            d.source_url,
            c.content AS chunk_content,
            1 - (c.embedding <=> %s::vector) AS similarity

        FROM legal_chunks c

        JOIN legal_documents d
            ON d.id = c.document_id

        WHERE d.document_type = 'CASE'
          AND d.category = %s

        ORDER BY c.embedding <=> %s::vector

        LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        embedding,
                        category,
                        embedding,
                        limit,
                    )
                )

                return cur.fetchall()
```

검색 시 다음 두 테이블을 JOIN한다.

``` text
legal_chunks
→ 검색 점수 / 검색된 내용

legal_documents
→ 사건번호 / 법원 / 판결결과 / 출처
```

------------------------------------------------------------------------

## 6. 첫 번째 핵심 Tool: `search_cases`

이 Tool이 프로젝트에서 가장 중요하다.

### Service

``` python
# legal_mcp/services/legal_search_service.py

from legal_mcp.providers.embedding import create_embedding
from legal_mcp.repositories.legal_repository import LegalRepository

class LegalSearchService:

    def __init__(self):
        self.repository = LegalRepository()

    def search_cases(
        self,
        query: str,
        category: str,
        top_k: int = 3,
    ):

        query_embedding = create_embedding(query)

        rows = self.repository.search_cases(
            embedding=query_embedding,
            category=category,
            limit=top_k,
        )

        return rows
```

### Tool

``` python
# legal_mcp/tools/case_tools.py

from mcp.server.fastmcp import FastMCP
from legal_mcp.services.legal_search_service import LegalSearchService

service = LegalSearchService()

def register_case_tools(mcp: FastMCP):

    @mcp.tool()
    def search_cases(
        query: str,
        category: str,
        top_k: int = 3,
    ) -> dict:
        # 사용자의 사례와 의미적으로 유사한 실제 판례를 검색한다.

        results = service.search_cases(
            query=query,
            category=category,
            top_k=top_k,
        )

        return {
            "success": True,
            "data": {
                "items": results
            },
            "meta": {
                "query": query,
                "category": category,
                "result_count": len(results),
                "retrieval_method": "vector",
            },
            "error": None,
        }
```

사용자가 다음과 같이 질문한다고 가정한다.

``` text
퇴직했는데 회사에서 퇴직금을 안 줬어요.
```

Agent가 다음과 같이 호출한다.

``` json
{
  "query": "퇴직했는데 회사에서 퇴직금을 지급하지 않았습니다.",
  "category": "labor",
  "top_k": 3
}
```

MCP 내부 흐름:

``` text
search_cases
 ↓
Embedding
 ↓
pgvector
 ↓
legal_chunks
 ↓
legal_documents JOIN
 ↓
판례 Top 3
```

결과 예:

``` json
{
  "success": true,
  "data": {
    "items": [
      {
        "document_id": 24,
        "case_number": "2022다12345",
        "case_name": "퇴직금",
        "court": "대법원",
        "decided_at": "2023-04-12",
        "judgment_result": "원고 일부 승소",
        "summary": "...",
        "source_url": "...",
        "similarity": 0.87
      }
    ]
  }
}
```

------------------------------------------------------------------------

## 7. 두 번째 Tool: `get_case_detail`

`search_cases`는 후보를 찾는 Tool이고, `get_case_detail`은 선택한 판례의
원문을 가져오는 Tool이다.

``` python
def get_case_detail(self, document_id: int):

    sql = """
    SELECT
        id,
        external_id,
        case_number,
        case_name,
        court,
        decided_at,
        judgment_result,
        summary,
        content,
        source_name,
        source_url
    FROM legal_documents
    WHERE id = %s
      AND document_type = 'CASE'
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (document_id,))
            return cur.fetchone()
```

Tool:

``` python
@mcp.tool()
def get_case_detail(document_id: int) -> dict:

    item = repository.get_case_detail(document_id)

    if item is None:
        return {
            "success": False,
            "data": None,
            "meta": {},
            "error": {
                "code": "CASE_NOT_FOUND",
                "message": "해당 판례를 찾을 수 없습니다."
            }
        }

    return {
        "success": True,
        "data": item,
        "meta": {},
        "error": None,
    }
```

주요 반환 정보:

``` text
사건번호
사건명
법원
선고일
판단 요지
실제 판결 결과
원문 출처
```

------------------------------------------------------------------------

## 8. 세 번째 Tool: `get_law_article`

정확한 법령명과 조문 번호를 알고 있는 경우 Vector Search가 아니라 일반
SQL 중심으로 검색한다.

예:

``` text
근로기준법 제36조 알려줘
```

Repository:

``` python
def get_law_article(
    self,
    law_name: str,
    article_number: str,
):

    sql = """
    SELECT
        id,
        law_name,
        article_number,
        title,
        content,
        effective_date,
        source_name,
        source_url

    FROM legal_documents

    WHERE document_type = 'LAW'
      AND law_name = %s
      AND article_number = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    law_name,
                    article_number
                )
            )

            return cur.fetchone()
```

Tool:

``` python
@mcp.tool()
def get_law_article(
    law_name: str,
    article_number: str,
) -> dict:

    item = repository.get_law_article(
        law_name,
        article_number,
    )

    if item is None:
        return {
            "success": False,
            "data": None,
            "meta": {},
            "error": {
                "code": "LAW_NOT_FOUND",
                "message": "해당 법령 또는 조문을 찾지 못했습니다."
            }
        }

    return {
        "success": True,
        "data": item,
        "meta": {},
        "error": None,
    }
```

------------------------------------------------------------------------

## 9. 네 번째 Tool: `search_legal_documents`

이 Tool은 법령 + 판례를 한 번에 찾는 Tool이다.

``` text
search_cases
→ CASE만 검색

get_case_detail
→ 판례 원문

get_law_article
→ 정확한 법령/조문

search_legal_documents
→ LAW + CASE 통합 검색
```

입력:

``` json
{
  "query": "퇴직 후 퇴직금을 받지 못한 상황",
  "category": "labor",
  "document_types": [
    "LAW",
    "CASE"
  ],
  "top_k": 3
}
```

이 Tool에는 향후 Hybrid Search를 구현한다.

``` text
Vector Score × 0.7
+
Keyword Score × 0.3
```

자연어 사례는 Vector Search 중심, 정확한 법령·조문·사건번호는
Keyword/SQL Search 중심으로 처리한다.

------------------------------------------------------------------------

## 10. `server.py`

모든 Tool을 Legal MCP Server에 등록한다.

``` python
import os

from mcp.server.fastmcp import FastMCP

from legal_mcp.tools.case_tools import register_case_tools
from legal_mcp.tools.law_tools import register_law_tools
from legal_mcp.tools.search_tools import register_search_tools

MCP_HOST = os.getenv(
    "MCP_HOST",
    "0.0.0.0"
)

MCP_PORT = int(
    os.getenv(
        "MCP_PORT",
        "8010"
    )
)

mcp = FastMCP(
    "legal-research-mcp",

    instructions=(
        "법령과 실제 판례를 검색하는 MCP Server입니다. "
        "검색 결과와 공식 출처만 반환하며 "
        "사용자의 승소 또는 패소를 예측하지 않습니다."
    ),

    host=MCP_HOST,
    port=MCP_PORT,

    stateless_http=True,
    json_response=True,
)

register_case_tools(mcp)
register_law_tools(mcp)
register_search_tools(mcp)

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http"
    )
```

실제 구현 시 사용하는 MCP Python SDK 버전에 따라 FastMCP import 경로와
Server API가 달라질 수 있으므로 프로젝트에서 설치한 `mcp` 버전에 맞춰
확정한다.

------------------------------------------------------------------------

## 11. MCP Server 3개보다 우선 1개를 추천

현재 계획에서는 `mcp_server1`, `mcp_server2`, `mcp_server3`을 카테고리별
서버 후보로 둘 수 있지만 MVP에서는 다음처럼 하나의 Legal MCP Server를
사용하는 것을 권장한다.

``` text
Legal MCP Server 하나

├─ housing 검색
├─ labor 검색
└─ consumer 검색
```

Tool에 이미 `category`가 들어가므로 서버를 굳이 세 개 만들 필요가 없다.

``` python
search_cases(
    category="housing"
)

search_cases(
    category="labor"
)

search_cases(
    category="consumer"
)
```

``` text
HousingAgent ─────┐
LaborAgent ───────┼→ Legal MCP
ConsumerAgent ────┘
```

향후 규모가 커졌을 때만 다음처럼 나눈다.

``` text
Housing MCP
Labor MCP
Consumer MCP
```

------------------------------------------------------------------------

## 12. Agent 3개의 역할

``` text
MCP
= 실제 검색 담당

Agent
= 어떤 검색을 할지 판단
```

예를 들어 HousingAgent:

``` text
사용자:
"보증금을 못 받았습니다."

HousingAgent 판단

1. 유사 판례 검색
   ↓
   search_cases

2. 관련 법령 검색
   ↓
   search_legal_documents

3. 특정 판례가 중요함
   ↓
   get_case_detail

4. 특정 조문 확인
   ↓
   get_law_article
```

LaborAgent와 ConsumerAgent도 동일한 Tool을 사용하되 각각 `labor`,
`consumer` category를 전달한다.

------------------------------------------------------------------------

## 13. 가장 중요한 MCP Tool 계약

팀원끼리는 Tool Input/Output을 확실하게 합의한다.

``` text
search_cases
──────────────────

Input

query
category
top_k


Output

document_id
case_number
case_name
court
decided_at
judgment_result
summary
source_url
similarity
```

공통 응답:

``` json
{
  "success": true,
  "data": {
    "items": []
  },
  "meta": {
    "query": "...",
    "category": "labor",
    "result_count": 3,
    "retrieval_method": "hybrid"
  },
  "error": null
}
```

실패 응답:

``` json
{
  "success": false,
  "data": null,
  "meta": {},
  "error": {
    "code": "DATABASE_ERROR",
    "message": "법률 데이터 검색 중 오류가 발생했습니다."
  }
}
```

이 계약을 지키면 다음 담당자가 독립적으로 작업할 수 있다.

``` text
지혜
DB 변경

병훈
MCP 구현

다혁
Agent 구현
```

------------------------------------------------------------------------

## 14. 개발 순서

``` text
① DB 팀

legal_documents
legal_chunks
Mock 데이터 준비

        ↓

② MCP

database.py
 ↓
embedding.py
 ↓
repository.py
 ↓
search_cases
 ↓
get_case_detail
 ↓
get_law_article
 ↓
search_legal_documents

        ↓

③ MCP 단독 테스트

search_cases(
    "퇴직금을 받지 못했습니다",
    "labor"
)

        ↓

④ Agent 연결

LaborAgent
 ↓
MCP Client
 ↓
search_cases

        ↓

⑤ Frontend 연결
```

DB/RAG는 먼저 Mock Data → PostgreSQL → Chunking → Embedding → pgvector →
MCP Server 흐름을 완성하고, 이후 Mock 데이터를 실제 Open API 데이터로
교체한다.

------------------------------------------------------------------------

## 15. 가장 먼저 완성할 기능

MCP 작업의 첫 번째 목표는 `search_cases` 하나의 End-to-End 흐름을
완성하는 것이다.

``` text
사용자 질문

"퇴직금을 못 받았습니다."

        ↓

search_cases

        ↓

Embedding

        ↓

legal_chunks
pgvector 검색

        ↓

legal_documents JOIN

        ↓

Top 3

        ↓

MCP JSON

        ↓

Agent
```

이 한 줄을 먼저 완성한다.

그다음:

``` text
search_cases
        ↓
get_case_detail
        ↓
get_law_article
        ↓
search_legal_documents
```

순서로 Tool을 늘린다.

DB가 구현됐다고 가정하면 MCP 작업 시작점은 **서버부터 만드는 것보다
`DB 연결 → Repository → search_cases → MCP Tool 등록` 순서**로 보는 것이
적절하다.

------------------------------------------------------------------------

## 16. 최종 역할 정리

``` text
PostgreSQL
= 법령·판례 원문 및 Metadata 저장

pgvector
= 사용자 사례와 의미적으로 유사한 Chunk 검색

Embedding Provider
= 사용자 Query를 Vector로 변환

Repository
= SQL / pgvector 검색 담당

Service
= 검색 흐름 및 결과 가공

MCP Tool
= Agent가 호출할 수 있는 검색 기능 제공

Legal MCP Server
= Tool 등록 및 MCP 통신 담당

Agent
= 상황에 따라 필요한 Tool 선택

LLM
= Tool Result에 포함된 공식 근거를 기반으로 설명

Backend
= Agent 실행 및 최종 응답 관리

Frontend
= 사용자 입력 및 검색 결과 표시
```

최종 목표는 **MCP Server가 법률적 결론을 만드는 것이 아니라 PostgreSQL +
pgvector에 저장된 공식 법령·판례를 안정적으로 검색하고, Agent가 사용할
수 있는 일관된 Tool Result로 제공하는 것**이다.
