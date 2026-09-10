# 생활 법률 검색 AI Agent 명세서

## 1. 문서 개요

| 항목 | 내용 |
|---|---|
| 시스템명 | 생활 법률 검색 AI Agent |
| 문서 버전 | MVP v0.1 |
| 대상 분야 | 임대차·주거, 근로·임금, 소비자·중고거래 |
| 개발 범위 | 3일, 4인 팀의 1차 MVP |
| 핵심 목표 | 사용자 질문에 적합한 Agent와 MCP Tool을 선택하고 검색 근거와 출처가 포함된 답변 제공 |
| 비목표 | 법률 자문, 승소 가능성 예측, 법률 판단 확정 |

AI Agent는 사용자의 법률 질문을 분야별로 분류하고 적절한 MCP 검색 Tool을 선택하며, 검색된 근거 안에서만 관련 법령·유사 사례·출처·주의사항이 포함된 답변을 생성한다.

## 2. 시스템 처리 구조

```text
Frontend
  -> FastAPI Router
  -> LegalQuestionService
  -> CategoryClassifier
  -> AgentRegistry
       |- HousingAgent
       |- LaborAgent
       `- ConsumerAgent
  -> MCP Client
       |- search_laws
       |- search_cases
       `- get_law_article
  -> PostgreSQL + pgvector / 외부 법률 데이터
  -> Agent 근거 기반 답변 생성
  -> 출처 검증
  -> Frontend 응답
```

## 3. Agent 구성

### 3.1 HousingAgent

| 항목 | 내용 |
|---|---|
| 클래스명 | `HousingAgent` |
| 카테고리 | `housing` |
| 담당 질문 | 임대차, 보증금, 계약갱신, 임대인·임차인 분쟁 |
| 기본 검색 | 법령 키워드 검색 + 유사 사례 벡터 검색 |
| 주요 확인 정보 | 계약 유형, 보증금, 계약 기간, 통지 여부 |
| 금지사항 | 보증금 반환 가능성이나 소송 승소 여부 단정 |

예시 질문:

```text
임대차 계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다.
```

예상 Tool 호출:

```text
search_laws(query=질문, category="housing", top_k=3)
search_cases(query=질문, category="housing", top_k=3)
```

### 3.2 LaborAgent

| 항목 | 내용 |
|---|---|
| 클래스명 | `LaborAgent` |
| 카테고리 | `labor` |
| 담당 질문 | 임금 체불, 해고, 근로계약, 퇴직금, 근로시간 |
| 기본 검색 | 법령 키워드 검색 + 유사 사례 벡터 검색 |
| 주요 확인 정보 | 계약 형태, 근무 기간, 임금 지급 내역, 해고 통지 |
| 금지사항 | 근로자성, 부당해고, 임금 체불 여부 확정 |

예시 질문:

```text
퇴직했는데 마지막 달 급여와 퇴직금을 받지 못했습니다.
```

### 3.3 ConsumerAgent

| 항목 | 내용 |
|---|---|
| 클래스명 | `ConsumerAgent` |
| 카테고리 | `consumer`, `secondhand` |
| 담당 질문 | 중고거래, 환불, 상품 하자, 전자상거래, 소비자 분쟁 |
| 기본 검색 | 법령 키워드 검색 + 유사 사례 벡터 검색 |
| 주요 확인 정보 | 거래 방식, 결제 방식, 상품 설명, 하자 상태, 판매자 대응 |
| 금지사항 | 사기죄 성립, 기망행위, 환불 가능성 확정 |

예시 질문:

```text
중고거래로 돈을 보냈는데 판매자가 연락을 끊었습니다.
```

## 4. 공통 Agent 인터페이스

세 Agent는 동일한 인터페이스를 구현하며, 공통 실행 로직은 `BaseLegalAgent`가 담당한다.

```python
class BaseLegalAgent:
    async def run(self, agent_input: AgentInput) -> AgentResult:
        """질문 검색 및 답변 생성 전체 흐름."""

    def plan_tool_calls(self, question: str) -> list[ToolCall]:
        """분야에 맞는 MCP Tool 호출 계획 생성."""

    async def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
    ) -> list[Evidence]:
        """계획된 MCP Tool 실행."""

    async def generate_answer(
        self,
        agent_input: AgentInput,
        evidence: list[Evidence],
        tool_calls: list[ToolCall],
    ) -> AgentResult:
        """검색 근거만 이용하여 답변 생성."""

    def validate_result(self, result: AgentResult) -> None:
        """근거, 출처, 안전 문구 검증."""

    def build_fallback_result(
        self,
        agent_input: AgentInput,
        tool_calls: list[ToolCall],
    ) -> AgentResult:
        """검색 결과가 없을 때 대체 응답 생성."""
```

Agent별 구현은 검색 카테고리와 시스템 프롬프트만 다르게 구성한다.

```python
class HousingAgent(BaseLegalAgent):
    category = "housing"
    system_prompt = HOUSING_SYSTEM_PROMPT


class LaborAgent(BaseLegalAgent):
    category = "labor"
    system_prompt = LABOR_SYSTEM_PROMPT


class ConsumerAgent(BaseLegalAgent):
    category = "consumer"
    system_prompt = CONSUMER_SYSTEM_PROMPT
```

## 5. 입력 명세

### 5.1 HTTP 요청

```http
POST /api/legal/questions
Content-Type: application/json
```

```json
{
  "question": "퇴직했는데 마지막 달 급여를 받지 못했습니다.",
  "category": null
}
```

| 필드 | 타입 | 필수 | 조건 |
|---|---|---:|---|
| `question` | `string` | 필수 | 2자 이상, 2,000자 이하 |
| `category` | `string \| null` | 선택 | `housing`, `labor`, `consumer`, `secondhand` |

`category`가 없으면 `CategoryClassifier`가 질문을 분류한다.

```python
class AgentInput(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    category: LegalCategory
```

## 6. 카테고리 분류 명세

```python
async def classify(question: str) -> LegalCategory:
    ...
```

| 질문 내용 | 분류 결과 |
|---|---|
| 임대차, 월세, 전세, 보증금 | `housing` |
| 임금, 해고, 퇴직금, 근로계약 | `labor` |
| 환불, 상품 하자, 소비자 피해 | `consumer` |
| 중고거래, 개인 판매자 | `secondhand` |
| 분류할 수 없음 | `unknown` |

`secondhand`는 `ConsumerAgent`가 처리한다. 분류 결과가 `unknown`이면 임의로 Agent를 선택하지 않고 추가 정보 요청 응답을 반환한다.

```python
AGENT_MAPPING = {
    LegalCategory.HOUSING: HousingAgent,
    LegalCategory.LABOR: LaborAgent,
    LegalCategory.CONSUMER: ConsumerAgent,
    LegalCategory.SECONDHAND: ConsumerAgent,
}
```

## 7. Tool 선택 규칙

| 질문 유형 | 검색 방법 | Tool |
|---|---|---|
| 정확한 법령·조문 요청 | SQL/키워드 | `get_law_article` |
| 적용 가능한 법률 질문 | 키워드 검색 | `search_laws` |
| 비슷한 상황·사례 질문 | 벡터 검색 | `search_cases` |
| 일반적인 생활 법률 분쟁 | 하이브리드 검색 | `search_laws`, `search_cases` |

일반적인 상황형 질문은 기본적으로 다음 두 Tool을 호출한다.

```python
[
    ToolCall(
        tool_name="search_laws",
        arguments={
            "query": question,
            "category": category,
            "top_k": 3,
        },
    ),
    ToolCall(
        tool_name="search_cases",
        arguments={
            "query": question,
            "category": category,
            "top_k": 3,
        },
    ),
]
```

특정 조문이 명시된 질문은 정확한 조문과 관련 사례를 함께 검색한다.

```python
[
    ToolCall(
        tool_name="get_law_article",
        arguments={
            "law_name": "근로기준법",
            "article_number": "36",
        },
    ),
    ToolCall(
        tool_name="search_cases",
        arguments={
            "query": question,
            "category": "labor",
            "top_k": 3,
        },
    ),
]
```

## 8. MCP Tool 명세

### 8.1 search_laws

관련 법령을 SQL 또는 키워드 검색으로 조회한다.

```python
async def search_laws(
    query: str,
    category: str,
    top_k: int = 3,
) -> list[Evidence]:
    ...
```

### 8.2 search_cases

사용자 상황과 유사한 사례를 벡터 검색한다.

```python
async def search_cases(
    query: str,
    category: str,
    top_k: int = 3,
) -> list[Evidence]:
    ...
```

### 8.3 get_law_article

법률명과 조문 번호가 명확할 때 정확한 조문을 조회한다.

```python
async def get_law_article(
    law_name: str,
    article_number: str,
) -> Evidence | None:
    ...
```

## 9. 공통 데이터 모델

```python
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class LegalCategory(StrEnum):
    HOUSING = "housing"
    LABOR = "labor"
    CONSUMER = "consumer"
    SECONDHAND = "secondhand"
    UNKNOWN = "unknown"


class ToolName(StrEnum):
    SEARCH_LAWS = "search_laws"
    SEARCH_CASES = "search_cases"
    GET_LAW_ARTICLE = "get_law_article"


class ToolCall(BaseModel):
    tool_name: ToolName
    arguments: dict[str, Any]


class Source(BaseModel):
    source_id: str
    title: str
    source_type: Literal["law", "case", "external"]
    url: str | None = None


class Evidence(BaseModel):
    evidence_id: str
    title: str
    content: str
    source: Source
    score: float | None = None


class AgentResult(BaseModel):
    category: LegalCategory
    answer: str
    related_laws: list[Evidence]
    similar_cases: list[Evidence]
    search_basis: list[str]
    sources: list[Source]
    cautions: list[str]
    tool_calls: list[ToolCall]
```

## 10. 최종 출력 명세

```json
{
  "category": "labor",
  "answer": "검색된 자료에 따르면 퇴직 후 임금 지급 기한과 관련된 법령을 우선 확인할 필요가 있습니다.",
  "related_laws": [
    {
      "evidence_id": "law-001",
      "title": "근로기준법 제36조",
      "content": "검색된 조문 내용",
      "source": {
        "source_id": "source-001",
        "title": "국가법령정보센터",
        "source_type": "law",
        "url": "https://example.com/law/001"
      },
      "score": 0.96
    }
  ],
  "similar_cases": [],
  "search_basis": [
    "질문의 임금 미지급 및 퇴직 상황을 기준으로 검색했습니다."
  ],
  "sources": [
    {
      "source_id": "source-001",
      "title": "국가법령정보센터",
      "source_type": "law",
      "url": "https://example.com/law/001"
    }
  ],
  "cautions": [
    "구체적인 판단은 계약 내용과 사실관계에 따라 달라질 수 있습니다.",
    "이 답변은 일반적인 법률정보이며 법률 자문이 아닙니다."
  ],
  "tool_calls": [
    {
      "tool_name": "search_laws",
      "arguments": {
        "query": "퇴직했는데 마지막 달 급여를 받지 못했습니다.",
        "category": "labor",
        "top_k": 3
      }
    }
  ]
}
```

## 11. 답변 생성 규칙

Agent는 다음 순서로 답변을 작성한다.

1. 질문 내용 요약
2. 검색된 관련 법령 설명
3. 검색된 유사 사례 설명
4. 현재 자료로 확인 가능한 범위
5. 추가로 확인할 사실관계
6. 출처 표시
7. 법률정보 제공에 관한 주의사항

### 필수 규칙

- 법령명, 조문, 사건번호는 검색 결과에 있을 때만 사용한다.
- 검색되지 않은 내용을 일반 지식으로 보완하지 않는다.
- 각 법령 및 사례는 `source_id`와 연결한다.
- 사실관계가 부족하면 부족한 항목을 명시한다.
- 검색 결과가 없으면 답변을 추측하지 않는다.
- 법률 자문이나 승소 가능성을 확정적으로 표현하지 않는다.

### 권장 표현

```text
검색된 자료에 따르면 검토할 수 있습니다.
구체적인 사실관계에 따라 판단이 달라질 수 있습니다.
현재 검색 결과만으로 확정하기 어렵습니다.
다음 사항을 추가로 확인할 필요가 있습니다.
```

### 금지 표현

```text
무조건 승소합니다.
명백한 불법입니다.
100% 환불받을 수 있습니다.
반드시 사기죄가 성립합니다.
```

## 12. 오류 및 예외 처리

| 상황 | 처리 방식 |
|---|---|
| 질문 누락 또는 형식 오류 | HTTP `422` |
| 지원하지 않는 카테고리 | HTTP `400` 또는 추가 질문 응답 |
| MCP 연결 실패 | HTTP `503` |
| MCP 응답 시간 초과 | HTTP `504` |
| 검색 결과 없음 | HTTP `200`, 근거 부족 응답 |
| LLM 응답 형식 오류 | 1회 재시도 후 HTTP `502` |
| 출처 누락 | 최종 답변 반환 중단 및 검증 오류 기록 |
| 일부 Tool 실패 | 성공한 근거로 답변하되 오류와 제한 명시 |
| 모든 Tool 실패 | 근거 부족 응답 또는 HTTP `503` |

검색 결과가 없는 것은 서버 오류가 아니므로 HTTP `200`으로 처리한다.

## 13. 실행 제한

```python
MAX_TOOL_CALLS = 3
TOOL_TIMEOUT_SECONDS = 10
LLM_TIMEOUT_SECONDS = 20
MAX_RETRY_COUNT = 1
DEFAULT_TOP_K = 3
MAX_QUESTION_LENGTH = 2000
```

무한 Tool 호출을 방지하기 위해 Agent 한 번의 실행에서 최대 3회까지만 허용한다.

## 14. 로깅 명세

Agent 실행마다 `request_id`를 생성하고 다음 내용을 기록한다.

```json
{
  "request_id": "uuid",
  "category": "labor",
  "agent": "LaborAgent",
  "question_length": 28,
  "tool_calls": [
    "search_laws",
    "search_cases"
  ],
  "evidence_count": 5,
  "duration_ms": 1850,
  "status": "success"
}
```

기본 로그 항목:

- `request_id`
- 선택된 Agent
- 선택된 Tool
- Tool별 실행 시간
- 검색 결과 개수
- 최종 처리 시간
- 오류 유형

질문 전문과 개인정보는 운영 로그에 그대로 저장하지 않는 것을 원칙으로 한다.

## 15. 핵심 클래스 및 함수명

```text
LegalQuestionService.answer_question()
CategoryClassifier.classify()
AgentRegistry.get()

BaseLegalAgent.run()
BaseLegalAgent.plan_tool_calls()
BaseLegalAgent.execute_tool_calls()
BaseLegalAgent.generate_answer()
BaseLegalAgent.validate_result()
BaseLegalAgent.build_fallback_result()

HousingAgent
LaborAgent
ConsumerAgent

LegalMCPClient.search_laws()
LegalMCPClient.search_cases()
LegalMCPClient.get_law_article()
```

## 16. MVP 완료 조건

- 질문에 맞는 Agent가 선택된다.
- 선택된 Agent가 적절한 MCP Tool을 호출한다.
- 법령과 사례가 각각 최대 Top 3까지 반환된다.
- 최종 답변은 실제 Tool 검색 결과만 사용한다.
- 법령과 사례에 출처가 포함된다.
- 검색 근거가 없으면 추측성 답변을 생성하지 않는다.
- 법률 자문이나 승소 가능성을 단정하지 않는다.
- MCP 오류 및 타임아웃이 처리된다.
- Agent 선택과 Tool 호출 내역이 로그로 남는다.

## 17. MVP 대표 성공 시나리오

```text
사용자 질문
  -> CategoryClassifier가 분야 분류
  -> AgentRegistry가 담당 Agent 선택
  -> Agent가 MCP Tool 호출 계획 생성
  -> search_laws 및 search_cases 실행
  -> 법령/사례 Top 3 수집
  -> LLM이 검색 근거만 사용해 답변 정리
  -> 출처 및 주의사항 검증
  -> Frontend에 최종 응답 반환
```

최우선 성공 조건은 하나의 질문이 `질문 -> Agent -> MCP Tool -> RAG -> 법령/사례 Top 3 -> 출처 포함 답변`으로 끝까지 처리되는 것이다.
