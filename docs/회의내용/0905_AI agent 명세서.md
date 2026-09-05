# 생활 법률 검색 AI Agent 아키텍처 설계서

> 문서 버전: MVP v1.0
>
> 작성일: 2026-09-04
>
> 대상 시스템: 생활 법률 검색 AI Agent
>
> 관련 계획: `docs/최종 plan.md`

## 1. 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 프로젝트명 | 생활 법률 검색 AI Agent(LawPath) |
| 목적 | 사용자의 생활 법률 상황과 관련된 공식 법령·실제 판례를 검색하여 출처와 함께 쉽게 설명한다. |
| AI Agent | 선택된 전문 Agent가 LLM을 통해 MCP Tool과 다음 행동을 결정한다. |
| Agent 실행 | 공통 Python AgentRuntime이 Model 호출, Tool 실행, 재판단과 종료를 관리한다. |
| Tool 연결 | Streamable HTTP 기반 Legal MCP Server 1개 |
| Backend / Frontend | FastAPI / Streamlit |
| Database | PostgreSQL + pgvector |
| 임시 저장 | Redis 최근 문맥, 요청 상태, Tool Timeline과 검색 Cache |
| 데이터 소스 | 국가법령정보 공동활용 Open API |
| 초기 데이터 | 공식 출처를 확인한 결정적인 Seed 데이터 |

이 서비스는 법률정보 검색 서비스이며 법률 자문, 범죄 성립 판단 또는 승패 예측을 제공하지 않는다.

## 2. 설계 범위

MVP는 세 개의 독립적인 전문 Single Agent를 하나의 Registry와 Runtime으로 관리한다.

```text
HousingAgent  → 임대차·주거
LaborAgent    → 근로·임금
ConsumerAgent → 소비자·중고거래
```

질문 하나에는 Agent 하나만 선택한다. Agent끼리 메시지를 주고받거나 서로 호출하지 않으므로 Coordinator 기반 Multi-Agent 구조가 아니다.

```text
1단계: LaborAgent + Mock Model + Mock Tool로 Loop 검증
2단계: 같은 Runtime에 HousingAgent와 ConsumerAgent Profile 추가
3단계: 실제 Legal MCP와 PostgreSQL/pgvector 연결
```

## 3. 핵심 설계 원칙

```text
AI Agent
= Goal + Instructions + Allowed Tools + State + LLM의 다음 행동 판단

Agent Runtime
= Model 호출 + Tool Call 추출 + MCP 실행 + Result 재전달 + 반복·종료

Backend Policy
= Tool Allowlist + arguments 검증 + 호출 제한 + 중복 실행 차단 + 안전 정책
```

LLM은 Tool과 arguments를 제안하지만 직접 실행하지 않는다. Python Backend가 호출을 검증하고 MCP Server에 실행을 요청한다. Agent와 Backend는 DB에 직접 접근하지 않는다.

## 4. 전체 시스템 구조

```text
Streamlit Frontend
        ↓ HTTP
FastAPI Router
        ↓
LegalQuestionService
        ↓ AgentProfile 선택
Agent Registry
        ↓
공통 Python AgentRuntime
   ├─ OpenAI Provider
   ├─ AgentState와 Trace
   ├─ Tool Allowlist/arguments Policy
   └─ 실행 횟수·Timeout Policy
        ↓ Streamable HTTP
Legal MCP Client
        ↓
Legal MCP Server
        ↓
LegalSearchService
        ↓
LegalRepository
        ↓
PostgreSQL + pgvector

Redis
├─ 최근 대화
├─ 요청 상태
├─ Tool Timeline
└─ RAG 검색 Cache
```

데이터 구축은 사용자 요청과 분리한다.

```text
국가법령정보 공동활용 Open API
→ Raw 수집 → Normalize → legal_documents
→ Chunking/Embedding → legal_chunks + pgvector
```

## 5. AgentProfile 공통 구조

```python
@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    goal: str
    description: str
    example_question: str
    instructions: str
    allowed_tools: frozenset[str]
```

| 필드 | 역할 |
| --- | --- |
| `agent_id` | API 요청과 Registry에서 Agent를 구분한다. |
| `name` | Frontend와 응답에 표시할 이름이다. |
| `goal` | Agent가 달성해야 하는 업무 목표다. |
| `description` | 담당 법률 분야를 설명한다. |
| `example_question` | Frontend에서 제공할 대표 질문이다. |
| `instructions` | Tool 선택, 근거 사용과 금지 행동을 안내한다. |
| `allowed_tools` | Agent가 호출할 수 있는 MCP Tool Allowlist다. |

```python
LEGAL_READ_TOOLS = frozenset({
    "search_laws", "search_cases", "get_law_article",
})
```

## 6. Agent별 설계

### 6.1 HousingAgent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `housing` |
| Goal | 임대차·주거 질문과 관련된 법령과 유사 판례를 검색한다. |
| 담당 | 전세·월세, 보증금, 계약 종료·갱신, 주택 관련 분쟁 |
| 대표 요청 | `계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다.` |
| Allowed Tools | `search_laws`, `search_cases`, `get_law_article` |

```text
사용자 요청 → 관련 임대차 법령 검색 → 유사 사실관계 검색
→ 필요한 조문 확인 → 부족한 사실 안내 → 근거 기반 최종 답변
```

### 6.2 LaborAgent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `labor` |
| Goal | 근로·임금 질문과 관련된 법령과 유사 판례를 검색한다. |
| 담당 | 임금 체불, 퇴직금, 해고, 근로계약, 근로시간 |
| 대표 요청 | `퇴직했는데 퇴직금을 받지 못했습니다.` |
| Allowed Tools | `search_laws`, `search_cases`, `get_law_article` |

```text
사용자 요청 → 노동 법령 검색 → 유사 판례 검색
→ Tool Result를 본 LLM이 추가 조회 판단
→ 부족한 사실 안내 → 근거 기반 최종 답변
```

### 6.3 ConsumerAgent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `consumer` |
| Goal | 소비자·중고거래 질문과 관련된 법령과 유사 판례를 검색한다. |
| 담당 | 온라인 거래, 환불, 미배송, 상품 하자, 중고거래 |
| 대표 요청 | `중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다.` |
| Allowed Tools | `search_laws`, `search_cases`, `get_law_article` |

`secondhand`는 별도 Agent가 아니라 ConsumerAgent의 내부 별칭이다. 정식 API category는 `consumer`다.

## 7. Agent Registry

```python
AGENT_REGISTRY = {
    "housing": HOUSING_AGENT,
    "labor": LABOR_AGENT,
    "consumer": CONSUMER_AGENT,
    "secondhand": CONSUMER_AGENT,
}
```

지원하지 않는 category는 Agent를 추측해 선택하지 않고 `UNSUPPORTED_CATEGORY`로 거부한다.

## 8. Tool 설계

| Tool | 입력 | 정상 출력 | 실패·빈 결과 | 위험도 |
| --- | --- | --- | --- | --- |
| `search_laws` | `query`, `category`, `top_k=3` | 법령 Evidence 최대 3개 | 결과 없음 `[]`, 오류 `SEARCH_ERROR` | `read` |
| `search_cases` | `query`, `category`, `top_k=3` | 판례 Evidence 최대 3개 | 결과 없음 `[]`, 오류 `SEARCH_ERROR` | `read` |
| `get_law_article` | `law_name`, `article_number` | 조문 Evidence 1개 | 결과 없음 `null` | `read` |

입력 제한:

- `query`: 공백 제거 후 5~2,000자
- `category`: `housing`, `labor`, `consumer`
- `top_k`: 기본 및 최대 3
- `law_name`, `article_number`: 빈 문자열 금지

### 8.1 Source와 Evidence

```python
class Source(BaseModel):
    source_id: str
    title: str
    source_type: Literal["law", "case", "external"]
    url: AnyHttpUrl


class Evidence(BaseModel):
    evidence_id: str
    document_id: str
    title: str
    content: str
    source: Source
    score: float | None = None
    law_name: str | None = None
    article_number: str | None = None
    case_number: str | None = None
    court: str | None = None
    decided_at: date | None = None
    judgment_result: str | None = None
```

`score`는 `0.0~1.0`이며 값이 클수록 검색 관련성이 높다. 승소 가능성을 의미하지 않는다.

### 8.2 ToolResult

```python
class ToolResult(BaseModel):
    success: bool
    tool: str
    data: list[Evidence] | Evidence | None
    error_code: str | None = None
    message: str | None = None
```

```text
검색 성공 + 결과 있음 → success=true, data=[Evidence]
검색 성공 + 결과 없음 → success=true, data=[]
조문 조회 결과 없음   → success=true, data=null
실행 실패              → success=false, error_code 지정
```

Embedding은 적재와 검색 모두 OpenAI `text-embedding-3-small`, 1,536차원을 사용한다.

## 9. MCP Tool 발견과 실행

```text
AgentRuntime 시작 → MCP tools/list
→ Profile.allowed_tools와 교집합 계산
→ 필수 Tool 존재 검사 → 허용된 Tool Schema만 Model에 전달
```

```text
Function Call 수신 → arguments JSON Parsing
→ JSON Object·Allowlist·Pydantic 검증
→ 중복 호출·호출 횟수 검사 → MCP tools/call
→ ToolResult를 function_call_output으로 구성
→ previous_response_id와 함께 Model에 전달
→ 다음 Tool 또는 최종 답변 판단
```

## 10. 공통 Python Agent Loop

```text
1. AgentProfile과 질문으로 AgentState 생성
2. 허용된 MCP Tool 발견
3. 최초 Model 호출
4. Function Call 이름과 arguments 검증
5. MCP Tool 실행
6. ToolResult와 Evidence를 State에 반영
7. ToolResult를 Model에 전달
8. 새 Tool Call이 있으면 반복
9. Tool Call이 없으면 최종 답변 저장
10. 근거가 없으면 no_evidence로 종료
11. 최대 Step 이후에도 Tool Call이 있으면 안전하게 중단
```

```text
MAX_AGENT_STEPS=4
MAX_TOOL_CALLS=3
MCP_TIMEOUT_SECONDS=10
LLM_TIMEOUT_SECONDS=20
MAX_MODEL_RETRIES=1
DEFAULT_TOP_K=3
MAX_QUESTION_LENGTH=2000
```

동일 Tool과 동일 arguments의 반복 실행은 금지한다.

## 11. 정상·비정상 입력과 분기

| 입력·상황 | Agent 행동 | 상태/오류 |
| --- | --- | --- |
| 지원 category의 구체적인 질문 | 해당 Agent를 선택하고 검색 | 정상 실행 |
| 사실관계가 일부 부족함 | 검색 가능한 근거와 추가 질문 제공 | 정상 또는 `no_evidence` |
| 빈 질문·5자 미만 | Model 호출 전 거부 | `INVALID_REQUEST` |
| 2,000자 초과 | Model 호출 전 거부 | `INVALID_REQUEST` |
| 지원하지 않는 category | Agent 선택하지 않음 | `UNSUPPORTED_CATEGORY` |
| 허용되지 않은 Tool | 실행하지 않음 | `invalid_tool_call` |
| 잘못된 Tool arguments | 실행하지 않음 | `invalid_tool_call` |
| 검색 결과 없음 | 추측하지 않고 부족함 표시 | `completed + no_evidence` |
| MCP/Model 오류 | 재시도·오류 정책 적용 | `mcp_tool_error`/`model_error` |
| 호출 제한 초과 | 추가 실행 없이 중단 | `max_steps_exceeded` |

## 12. AgentState

```python
class AgentState(BaseModel):
    request_id: str
    agent_id: str
    agent_name: str
    goal: str
    question: str
    model: str
    status: Literal["running", "completed", "failed", "stopped"]
    termination_reason: str | None = None
    current_step: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    evidence_count: int = 0
    trace: list[TraceEvent] = []
    answer: str | None = None
```

| ID | 역할 |
| --- | --- |
| `user_id` | 저장 기능에서 사용자를 식별하는 내부 ID |
| `session_id` | 비로그인 사용자의 일시적인 대화 세션 ID |
| `request_id`/`run_id` | 질문 한 건의 Agent 실행 UUID, MVP에서는 같은 값 |
| `agent_id` | 선택된 전문 Agent ID |

| `status` | `termination_reason` | 의미 |
| --- | --- | --- |
| `completed` | `model_finished` | 근거 기반 정상 답변 완료 |
| `completed` | `no_evidence` | 검색 성공, 관련 근거 없음 |
| `failed` | `startup_error` | Profile·Provider·Tool 발견 실패 |
| `failed` | `model_error` | Model 호출 실패 |
| `failed` | `invalid_tool_call` | Tool 이름 또는 arguments 오류 |
| `failed` | `mcp_tool_error` | MCP Tool 실행 실패 |
| `stopped` | `max_steps_exceeded` | 실행 제한 초과 |

한 종류의 검색만 성공하면 성공한 근거만으로 제한적 답변을 제공하고 누락된 근거를 명시한다. 모든 검색이 실패하면 법률 답변을 생성하지 않는다.

## 13. Trace 설계

Trace는 내부 추론이 아니라 검증 가능한 실행 사실만 기록한다.

| `owner` | 기록 예시 |
| --- | --- |
| `runtime` | 실행 시작, Model 오류, 최대 단계 초과 |
| `ai_agent` | Tool 선택, 최종 답변 생성 |
| `policy` | 허용 여부·arguments·중복 호출 검증 |
| `mcp` | Tool 발견과 실행 결과 |

```json
[
  {"owner": "runtime", "stage": "run_started"},
  {"owner": "mcp", "stage": "tools_discovered"},
  {"owner": "ai_agent", "stage": "model_selected_tool", "tool": "search_laws"},
  {"owner": "policy", "stage": "tool_call_validated"},
  {"owner": "mcp", "stage": "tool_executed", "result_count": 3},
  {"owner": "ai_agent", "stage": "model_final_answer"}
]
```

Trace에는 API Key, Token, DB URL, 불필요한 개인정보와 chain-of-thought를 기록하지 않는다. 일반 사용자에게 노출하지 않고 테스트 API 또는 운영 로그에서 확인한다.

## 14. Human-in-the-loop와 Tool 위험도

| 위험도 | 의미 | 실행 방식 |
| --- | --- | --- |
| `read` | 법령·판례 조회처럼 외부 상태를 변경하지 않음 | 검증 후 자동 실행 |
| `change` | 외부 데이터 생성·수정·삭제 | MVP Tool에 없음 |
| `forbidden` | Agent 범위 밖의 고위험 행동 | 항상 차단 |

현재 세 Legal Tool은 모두 `read`이므로 사용자 승인 대기 State가 필요하지 않다. Agent는 법적 신청, 신고, 계약 변경 또는 결제를 수행하지 않는다. 향후 상태 변경 Tool을 추가할 때만 승인 Snapshot, 명시적 승인, 멱등성과 Audit을 별도 설계한다. 사실관계가 부족해 추가 질문하는 것은 Human Approval이 아니라 정보 보완이다.

## 15. State 저장·Redis·Audit

| 저장 위치 | 역할 |
| --- | --- |
| Process State | 한 요청 안의 Agent Loop 상태 |
| Redis | 최근 문맥, 요청 상태, Tool Timeline, 검색 Cache |
| PostgreSQL | 사용자가 명시적으로 저장한 질문·답변·근거 |

`저장하기` 요청은 `source_request_id` Unique Constraint와 Transaction으로 중복 저장을 방지한다. Redis 장애가 발생해도 PostgreSQL/pgvector 검색은 계속 동작한다.

## 16. 법률 안전 정책

Agent는 MCP ToolResult의 Evidence만 근거로 사용한다.

- 검색되지 않은 법령명, 조문, 판례, 사건번호 또는 URL 생성 금지
- 승소·패소 확률과 결과 예측 금지
- 범죄 성립 여부 단정 금지
- 보증금·임금·환불을 반드시 받을 수 있다고 단정 금지
- 결과가 없을 때 Model 일반 지식으로 법적 결론 생성 금지

모든 응답에는 정보 제공 목적이며 전문가 상담을 대체하지 않는다는 주의문을 포함한다.

## 17. Backend API

| Method | Endpoint | 역할 |
| --- | --- | --- |
| `GET` | `/health` | Backend와 의존 서비스 상태 확인 |
| `GET` | `/api/legal/agents` | AgentProfile 목록 제공 |
| `POST` | `/api/legal/questions` | 전문 Agent 실행 |
| `GET` | `/api/legal/runs/{request_id}` | 개발·테스트용 State와 Trace 조회 |
| `POST` | `/api/conversations/save` | 선택한 질문·답변 영구 저장 |

```json
{
  "session_id": "web-uuid",
  "category": "labor",
  "question": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

```text
request_id, agent_id, status, termination_reason
question_summary, key_issues, answer
related_laws, similar_cases, sources
follow_up_questions, cautions, is_mock
```

Frontend 기준 화면에 맞춰 `related_laws`에는 법령명·조문·요약·공식 원문을, `similar_cases`에는 법원·사건 식별정보·선고일·판결 결과·유사한 점·score·공식 원문을 제공한다.

## 18. 파일별 책임

| 파일 | 책임 |
| --- | --- |
| `backend/app/agents/models.py` | AgentProfile, AgentState, TraceEvent |
| `backend/app/agents/housing_agent.py` | HousingAgent Profile |
| `backend/app/agents/labor_agent.py` | LaborAgent Profile |
| `backend/app/agents/consumer_agent.py` | ConsumerAgent Profile |
| `backend/app/agents/registry.py` | Agent 등록과 category 기반 조회 |
| `backend/app/agents/runtime.py` | Model·Tool 반복, State, 종료 처리 |
| `backend/app/providers/openai.py` | 최초·후속 Model 호출 |
| `backend/app/policies/tool_policy.py` | Allowlist, arguments, 중복 호출 검증 |
| `backend/app/mcp_clients/legal_mcp.py` | Legal MCP Tool 발견과 실행 |
| `backend/app/services/legal_question_service.py` | Router와 AgentRuntime 연결 |
| `legal_mcp/server.py` | Legal MCP Server 진입점 |
| `legal_mcp/tools/` | 세 Legal Tool 등록과 I/O |
| `legal_mcp/services/legal_search_service.py` | Hybrid Search와 결과 가공 |
| `legal_mcp/repositories/legal_repository.py` | SQL과 pgvector 검색 |

## 19. 테스트 기준

- 세 category가 올바른 AgentProfile을 선택하는가?
- 허용된 Tool만 발견하고 호출하는가?
- ToolResult를 관찰한 뒤 다음 행동을 재판단하는가?
- 잘못된 Tool과 arguments를 실행 전에 차단하는가?
- Tool Call이 없으면 정상 종료하는가?
- 최대 Step과 Tool 호출 수를 초과하면 안전하게 중단하는가?
- 결과 없음, MCP 오류와 Model 오류를 구분하는가?
- 최종 답변이 Evidence에만 근거하는가?
- 허위 사건번호·URL, 승패 예측과 범죄 단정을 생성하지 않는가?
- Trace가 실제 Tool 순서와 호출 횟수를 증명하는가?

## 20. 현재 한계와 운영 확장

| 현재 MVP | 운영 확장 |
| --- | --- |
| 공식 출처 기반 소량 Seed | 승인된 Open API 증분 수집 확대 |
| 사용자가 category 지정 | 검증된 자동 category 분류 |
| Redis 단기 State | 영구 State Store와 접근 제어 |
| 익명 session_id | 검증된 로그인 Session/Token |
| 초기 Hybrid 가중치 | 평가 기반 가중치 조정 |
| 읽기 전용 Tool | 필요 시 승인 기반 변경 Tool 추가 |

## 핵심 정리

```text
생활 법률 검색 AI Agent
= 분야별 Goal과 Tool 권한
+ 공통 Python Agent Loop
+ Legal MCP ToolResult 기반 LLM 재판단
+ AgentState와 Trace
+ 명시적인 종료·오류·법률 안전 정책
```

Agent는 단순 LLM 호출 함수가 아니다. 제한된 Tool을 가진 LLM이 State와 검색 결과를 관찰하며 다음 행동을 선택하고, Python Runtime이 검증·실행·종료를 통제하는 전체 구조다.
