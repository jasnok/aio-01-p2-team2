# 에이전트 아키텍처 설계서 샘플

> 이 문서는 다음 두 프로젝트의 실제 `backend/app/agents`와 MCP Tool 구현을 기반으로 작성한 샘플입니다.
>
> - `C:\mini_agent_st\mini_agent_06_agent_workflow`
> - `C:\mini_agent_st\mini_agent_07_human_approval`
>
> 샘플을 그대로 제출하지 말고 팀 프로젝트의 실제 Agent, Tool, State와 실행 흐름에 맞게 수정합니다.

## 1. 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 프로젝트명 | Independent Single Agent Service와 Safe Order Agent |
| 목적 | Goal과 Tool이 다른 AI Agent를 독립적으로 실행하고, 변경 Tool은 사용자 승인 후 실행한다. |
| AI Agent | OpenAI Model이 사용자 요청과 Tool Result를 보고 다음 Tool 또는 최종 답변을 판단한다. |
| Agent 실행 | 공통 순수 Python Runtime이 Model과 MCP Tool 사이의 반복을 관리한다. |
| Tool 연결 | Streamable HTTP MCP Server |
| Backend | FastAPI |
| Frontend | Streamlit |
| 기본 데이터 | 외부 API 대신 결정적인 Mock 데이터 |

## 2. 설계 범위

이 설계는 두 단계로 구성됩니다.

```text
06 Agent Workflow
→ Travel, Support, Order Agent를 사용자가 직접 선택
→ 선택된 Single Agent 하나가 독립적으로 실행
→ 읽기·검색·계산 Tool Result를 보고 LLM이 재판단

07 Human Approval
→ Order Agent 하나에 집중
→ 조회와 계산 Tool은 자동 실행
→ 실제 주문 생성 Tool은 실행하지 않고 중단
→ 사용자 승인 후 한 번만 실행하고 Agent Loop 재개
```

여러 Agent가 등록되어 있어도 Agent끼리 메시지를 주고받거나 서로 호출하지 않습니다. Coordinator, Handoff와 공유 State가 없으므로 Multi-Agent Orchestration이 아니라 **여러 개의 독립적인 Single AI Agent 서비스**입니다.

## 3. 핵심 설계 원칙

```text
AI Agent
= Goal
+ Instructions
+ Allowed Tools
+ State
+ LLM의 다음 행동 판단

Agent Runtime
= Model 호출
+ Tool Call 추출
+ MCP Tool 실행
+ Tool Result 재전달
+ 반복 및 종료 조건

Backend Policy
= Tool Allowlist
+ arguments 검증
+ 위험도 판단
+ 승인 대상 검증
+ 중복 실행 방지
```

LLM은 Tool을 선택하고 arguments를 제안하지만 직접 실행하지 않습니다. Python Backend가 Tool Call을 검증하고 MCP Server에 실행을 요청합니다.

## 4. 전체 시스템 구조

```text
Streamlit Frontend
        ↓ HTTP
FastAPI Router
        ↓
Agent Service
        ↓ Agent Profile 선택
Agent Registry
        ↓
공통 Python Agent Runtime
   ├─ OpenAI Provider
   ├─ 실행 State와 Trace
   ├─ Tool Allowlist 검사
   └─ 승인 Policy와 State Store
        ↓ Streamable HTTP
MCP Client
        ↓
MCP Tool Server
        ↓
Mock 여행·주문·고객지원 데이터
```

## 5. Agent Profile 공통 구조

두 프로젝트는 같은 `AgentProfile`을 사용합니다.

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
| `name` | 화면과 응답에 표시할 Agent 이름이다. |
| `goal` | Agent가 달성해야 하는 하나의 업무 목표다. |
| `description` | 사용자에게 Agent의 역할을 설명한다. |
| `example_question` | 화면에서 제공할 대표 질문이다. |
| `instructions` | Tool 호출 순서, 근거 사용과 금지 행동을 LLM에 안내한다. |
| `allowed_tools` | 해당 Agent가 발견하고 호출할 수 있는 Tool의 Allowlist다. |

Profile과 Runtime을 분리하므로 여러 Agent가 같은 실행 코드를 재사용하면서도 Goal과 Tool 권한은 서로 다르게 유지할 수 있습니다.

## 6. Agent별 설계

### 6.1 Travel Agent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `travel` |
| Goal | 현재 날씨에 맞는 여행 장소를 추천한다. |
| 대표 요청 | `제주 날씨에 맞는 장소를 추천해 줘.` |
| Allowed Tools | `get_weather`, `search_indoor_places`, `search_outdoor_places` |

판단 흐름:

```text
사용자 요청
→ get_weather
→ condition이 비인가?
   ├─ 예: search_indoor_places
   └─ 아니오: search_outdoor_places
→ Tool Result에 근거한 장소 추천
→ Tool Call 없이 최종 답변을 반환하면 종료
```

Python 코드가 비 여부를 직접 분기하지 않습니다. LLM이 날씨 Tool Result를 관찰하고 다음 장소 Tool을 선택합니다.

### 6.2 Customer Support Agent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `support` |
| Goal | 주문 상태와 고객 지원 정책을 근거로 문의에 답한다. |
| 대표 요청 | `ORDER-1001 배송 상태와 반품 가능 여부를 알려 줘.` |
| Allowed Tools | `get_order_status`, `search_return_policy` |

판단 흐름:

```text
사용자 요청
→ 배송 상태 질문이면 get_order_status
→ 반품 가능 여부 질문이면 search_return_policy
→ 두 정보가 모두 필요하면 두 Tool을 사용
→ 주문 상태와 정책을 종합한 최종 답변
```

### 6.3 Order Assistant Agent

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `order` |
| Goal | 상품과 재고를 확인하고 주문 예상 금액을 안내한다. |
| 대표 요청 | `무선 키보드 2개를 주문할 수 있는지와 예상 금액을 알려 줘.` |
| Allowed Tools | `search_product`, `check_inventory`, `calculate_order_total` |

판단 흐름:

```text
사용자 요청
→ search_product로 product_id와 가격 확인
→ check_inventory로 재고 확인
→ calculate_order_total로 수량별 예상 금액 계산
→ 실제 주문은 생성하지 않고 안내 후 종료
```

### 6.4 Safe Order Agent

`07_human_approval`에서는 Order Agent에 `place_order`를 추가합니다.

| 항목 | 내용 |
| --- | --- |
| `agent_id` | `order` |
| Goal | 상품·재고·금액을 확인하고 사용자가 승인하면 주문을 생성한다. |
| 대표 요청 | `무선 키보드 2개의 재고와 금액을 확인해서 주문해 줘.` |
| Allowed Tools | `search_product`, `check_inventory`, `calculate_order_total`, `place_order` |

```text
search_product             → read → 자동 실행
check_inventory            → read → 자동 실행
calculate_order_total      → read → 자동 실행
place_order                → change → 사용자 승인 전 중단
```

## 7. Tool 설계

### 7.1 여행 Tool

| Tool | 입력 | 정상 출력 | 실패·빈 결과 | 위험도 |
| --- | --- | --- | --- | --- |
| `get_weather` | `city: str` | `success`, `city`, `condition`, `temperature_c` | 등록되지 않은 도시는 `CITY_NOT_FOUND` | `read` |
| `search_indoor_places` | `city: str` | `success`, `city`, `category: indoor`, `items` | 빈 도시는 `INVALID_CITY`, 후보가 없으면 빈 `items` | `read` |
| `search_outdoor_places` | `city: str` | `success`, `city`, `category: outdoor`, `items` | 빈 도시는 `INVALID_CITY`, 후보가 없으면 빈 `items` | `read` |

예시:

```json
{
  "tool": "get_weather",
  "arguments": {"city": "제주"},
  "result": {
    "success": true,
    "city": "제주",
    "condition": "비",
    "temperature_c": 21
  }
}
```

### 7.2 고객 지원 Tool

| Tool | 입력 | 정상 출력 | 실패·빈 결과 | 위험도 |
| --- | --- | --- | --- | --- |
| `get_order_status` | `order_id: str` | `status`, `delivered`, `purchased_days_ago` | 주문이 없으면 `ORDER_NOT_FOUND` | `read` |
| `search_return_policy` | 없음 | 반품 가능 기간, 조건과 정책 출처 | 현재 Mock에서는 항상 정상 반환 | `read` |

예시:

```json
{
  "tool": "get_order_status",
  "arguments": {"order_id": "ORDER-1001"},
  "result": {
    "success": true,
    "order_id": "ORDER-1001",
    "status": "배송 중",
    "delivered": false,
    "purchased_days_ago": 3
  }
}
```

### 7.3 주문 조회·계산 Tool

| Tool | 입력 | 정상 출력 | 실패·검증 | 위험도 |
| --- | --- | --- | --- | --- |
| `search_product` | `query: str` | 상품별 `product_id`, `name`, `price` 목록 | 빈 검색어는 `INVALID_QUERY` 또는 빈 결과 | `read` |
| `check_inventory` | `product_id: str` | 현재 `stock` | 상품이 없으면 `PRODUCT_NOT_FOUND` | `read` |
| `calculate_order_total` | `product_id: str`, `quantity: int` | 수량, 단가와 `total` | 수량은 1 이상, 재고 부족은 `INSUFFICIENT_STOCK` | `read` |

`calculate_order_total`은 금액을 계산하지만 외부 상태를 바꾸지 않으므로 `read`로 처리합니다.

### 7.4 주문 생성 Tool

| Tool | 입력 | 정상 출력 | 실패·검증 | 위험도 |
| --- | --- | --- | --- | --- |
| `place_order` | `product_id: str`, `quantity: int` | `order_id`, 수량, 금액, 남은 재고 | 수량은 1 이상, 상품 없음과 재고 부족 검사 | `change` |

`place_order`는 주문을 생성하고 재고를 차감하므로 Model이 선택해도 바로 실행하지 않습니다.

```json
{
  "agent_id": "order",
  "tool": "place_order",
  "arguments": {
    "product_id": "P-KEYBOARD",
    "quantity": 2
  }
}
```

위 객체 전체가 사용자가 확인할 승인 Snapshot입니다.

## 8. MCP Tool 발견과 실행

```text
Agent Runtime 시작
→ MCP tools/list
→ Profile.allowed_tools에 포함된 Tool만 선택
→ 필요한 Tool이 MCP Server에 모두 있는지 검사
→ 선택된 Tool Schema만 OpenAI에 전달
```

LLM이 Tool을 선택하면 Runtime은 다음 순서로 실행합니다.

```text
Function Call 수신
→ arguments JSON Parsing
→ JSON Object인지 검사
→ Tool Allowlist 검사
→ MCP tools/call
→ Result를 function_call_output으로 구성
→ previous_response_id와 함께 OpenAI에 전달
→ LLM이 다음 Tool 또는 최종 답변 판단
```

## 9. 공통 Python Agent Loop

`06_agent_workflow`의 세 Agent는 같은 `run_single_agent()`를 사용합니다.

```text
1. Agent Profile과 사용자 질문으로 State 생성
2. 허용된 MCP Tool 발견
3. 최초 LLM 호출
4. Function Call이 있으면 Tool 실행
5. 모든 Tool Result를 LLM에 전달
6. LLM이 새로운 Tool을 선택하면 반복
7. Tool Call이 없으면 output_text를 최종 답변으로 저장
8. MAX_AGENT_STEPS 이후에도 Tool Call이 남으면 안전하게 중단
```

### 정상 종료 조건

```python
calls = [item for item in response.output if item.type == "function_call"]

if not calls:
    state["status"] = "completed"
    state["termination_reason"] = "model_finished"
    state["answer"] = response.output_text
```

### 실패와 중단 조건

| 상황 | `status` | `termination_reason` |
| --- | --- | --- |
| Tool 발견 또는 Client 생성 실패 | `failed` | `startup_error` |
| OpenAI 호출 실패 | `failed` | `model_error` |
| Tool 이름 또는 arguments 오류 | `failed` | `invalid_tool_call` |
| MCP Tool 실행 실패 | `failed` | `mcp_tool_error` |
| 최대 단계 뒤에도 Tool Call 존재 | `stopped` | `max_steps_exceeded` |
| Tool Call 없이 최종 답변 반환 | `completed` | `model_finished` |

## 10. Agent State

### 10.1 기본 Agent State

| 필드 | 타입 | 역할 |
| --- | --- | --- |
| `agent_id` | `str` | 실행 중인 Agent 구분 |
| `agent_name` | `str` | 사용자 표시 이름 |
| `goal` | `str` | 현재 Agent의 목표 |
| `question` | `str` | 사용자 요청 |
| `model` | `str` | 사용한 OpenAI Model |
| `status` | `str` | `running`, `completed`, `failed`, `stopped` |
| `termination_reason` | `str | None` | 완료·실패·중단 이유 |
| `llm_calls` | `int` | LLM 호출 횟수 |
| `tool_calls` | `int` | 실제 Tool 실행 횟수 |
| `trace` | `list[dict]` | 판단과 실행 과정 |
| `answer` | `str | None` | 최종 답변 |

### 10.2 승인 Agent 추가 State

| 필드 | 타입 | 역할 |
| --- | --- | --- |
| `run_id` | `str` | 승인 전후의 같은 실행을 식별 |
| `actor_id` | `str` | 실행을 요청하고 승인하는 사용자 식별자 |
| `response_id` | `str` | 승인 후 이전 OpenAI 응답에서 계속하기 위한 ID |
| `next_step` | `int` | 재개할 Agent Loop 단계 |
| `pending_call` | `dict` | 아직 실행하지 않은 `call_id`, Tool과 arguments |
| `pending_approval` | `dict` | 위험도, 승인 질문, Snapshot과 허용 결정값 |

`State`는 단순 출력 데이터가 아닙니다. Agent가 무엇을 관찰하고 몇 번 반복했는지 설명하고, 변경 Tool 직전에서 멈춘 실행을 나중에 이어 가는 근거입니다.

## 11. Trace 설계

Trace의 `owner`는 각 판단과 실행의 책임 주체를 구분합니다.

| `owner` | 기록 예시 |
| --- | --- |
| `runtime` | Agent 시작, Model 오류, 최대 단계 초과 |
| `ai_agent` | Model의 Tool 선택과 최종 답변 |
| `mcp` | Tool 발견과 실제 Tool 실행 |
| `policy` | 잘못된 호출, 금지 Tool 차단, 승인 대기 전환 |
| `human` | 사용자의 승인 또는 거절 |

```json
[
  {"owner": "runtime", "stage": "run_started"},
  {"owner": "mcp", "stage": "tools_discovered"},
  {"owner": "ai_agent", "stage": "model_selected_tool", "tool": "place_order"},
  {"owner": "policy", "stage": "paused_for_approval"},
  {"owner": "human", "stage": "change_approved"},
  {"owner": "mcp", "stage": "approved_change_executed"},
  {"owner": "ai_agent", "stage": "model_final_answer"}
]
```

## 12. Human Approval 실행 흐름

```text
사용자: 무선 키보드 2개를 주문해 줘
→ search_product 자동 실행
→ check_inventory 자동 실행
→ calculate_order_total 자동 실행
→ LLM이 place_order Tool Call 제안
→ Backend가 위험도를 change로 판단
→ Tool을 실행하지 않고 Snapshot과 State 저장
→ status = waiting_approval
→ 사용자 approve 또는 reject
```

### 승인

```text
승인 대기 State인가?
→ decision이 approve인가?
→ 승인 Snapshot이 저장된 Snapshot과 같은가?
→ Tool이 Agent Allowlist에 있는가?
→ 현재도 change Tool인가?
→ 같은 run_id와 call_id가 이미 처리됐는가?
→ place_order 한 번 실행
→ Tool Result를 OpenAI에 전달
→ Agent Loop 재개
→ 최종 답변
```

### 거절

```text
decision = reject
→ place_order 실행하지 않음
→ status = rejected
→ termination_reason = user_rejected
→ 거절 내용을 Audit Log에 기록
→ 종료
```

## 13. Tool 위험도 정책

| 위험도 | 의미 | 실행 방식 |
| --- | --- | --- |
| `read` | 조회·검색·계산처럼 외부 상태를 바꾸지 않음 | 자동 실행 |
| `change` | 주문 생성과 재고 차감처럼 외부 상태를 변경 | 승인 전 중단 |
| `forbidden` | Agent에 허용하지 않은 고위험 행동 | 승인 여부와 관계없이 차단 |

현재 정책:

```python
CHANGE_TOOLS = {"place_order"}
FORBIDDEN_TOOLS = {"make_payment", "change_user_role"}
```

Model의 Instructions는 행동을 안내하지만 보안 경계가 아닙니다. 최종 위험도는 Backend의 `action_risk()`가 결정합니다.

## 14. State 저장·멱등성·Audit

학습 프로젝트는 Process Memory를 사용합니다.

| 저장 구조 | 역할 |
| --- | --- |
| `RUNS` | `run_id`별 승인 대기와 실행 State 보관 |
| `PROCESSED_CALLS` | 같은 승인 요청의 중복 실행 방지 |
| `AUDIT_LOG` | 승인·거절과 실행 결과 기록 |

```text
call_key = run_id + pending_call.call_id
```

사용자가 승인 버튼을 두 번 누르거나 같은 HTTP 요청이 재전송되어도 `call_key`가 이미 처리됐다면 `place_order`를 다시 실행하지 않습니다.

운영 환경에서는 Process Memory를 Database Transaction, Unique Constraint와 영구 Audit Table로 교체해야 합니다.

## 15. Backend API

### Agent Workflow

| API | 역할 |
| --- | --- |
| Agent 목록 조회 | Agent Profile과 Allowed Tools 제공 |
| Agent 실행 | 사용자가 선택한 Agent 하나를 독립 실행 |

### Human Approval

| Method | Endpoint | 역할 |
| --- | --- | --- |
| `GET` | `/api/agents/mcp-status` | MCP Server와 Tool 상태 확인 |
| `POST` | `/api/agents/runs` | Safe Order Agent 시작 또는 승인 대기까지 진행 |
| `GET` | `/api/agents/runs/{run_id}` | 저장된 실행 State 조회 |
| `POST` | `/api/agents/runs/{run_id}/decision` | 승인·거절 결과 제출 및 실행 재개 |
| `GET` | `/api/agents/runs/{run_id}/audit` | 승인과 주문 실행 Audit 조회 |

승인 요청 Payload:

```json
{
  "actor_id": "user-01",
  "decision": "approve",
  "approval_target": {
    "agent_id": "order",
    "tool": "place_order",
    "arguments": {
      "product_id": "P-KEYBOARD",
      "quantity": 2
    }
  },
  "note": "상품과 수량 확인"
}
```

## 16. 파일별 책임

| 파일 | 책임 |
| --- | --- |
| `backend/app/agents/models.py` | 공통 `AgentProfile` 정의 |
| `backend/app/agents/travel_agent.py` | Travel Agent의 Goal·Instructions·Allowed Tools |
| `backend/app/agents/support_agent.py` | Support Agent의 Goal·Instructions·Allowed Tools |
| `backend/app/agents/order_agent.py` | Order Agent의 Goal·Instructions·Allowed Tools |
| `backend/app/agents/registry.py` | Agent 등록과 ID 기반 조회 |
| `backend/app/agents/runtime.py` | LLM·Tool 반복, 종료, 승인 중단과 재개 |
| `backend/app/mcp/client.py` | MCP Tool 발견과 실행 |
| `backend/app/providers/openai.py` | 최초·후속 OpenAI Responses 호출 |
| `backend/app/approval/policies.py` | Tool 위험도 분류 |
| `backend/app/approval/store.py` | 실행 State, 멱등성과 Audit 저장 |
| `backend/app/services/agent_service.py` | Router와 Agent Runtime 연결 |
| `mcp_server/business_tools_server.py` | Travel·Support·Order 조회 Tool 제공 |
| `mcp_server/order_tools_server.py` | 조회 Tool과 승인 대상 `place_order` 제공 |

## 17. 테스트 기준

### Agent Workflow

- Agent별로 허용된 Tool만 발견되는가?
- Travel Agent가 날씨 Result에 따라 실내 또는 야외 Tool을 선택하는가?
- Support Agent가 필요한 경우 주문 상태와 반품 정책을 모두 조회하는가?
- Order Agent가 상품 검색, 재고 확인과 금액 계산 순서를 지키는가?
- Tool Call이 없으면 정상 종료하는가?
- 최대 반복 횟수를 넘으면 안전하게 중단하는가?

### Human Approval

- `read` Tool은 승인 없이 실행되는가?
- `place_order`는 승인 전에 실행되지 않는가?
- 사용자가 거절하면 재고가 변경되지 않는가?
- 승인 Snapshot이 변경되면 실행을 차단하는가?
- 같은 승인 요청이 재전송되어도 주문이 한 번만 생성되는가?
- 승인·거절과 Tool Result가 Audit Log에 기록되는가?

## 18. 현재 한계와 운영 확장

| 현재 학습 구현 | 운영 확장 |
| --- | --- |
| Mock 상품·날씨·주문 데이터 | 실제 외부 API 또는 Database |
| Process Memory State | 영구 State Store |
| 메모리 `set` 멱등성 | Database Unique Constraint와 Transaction |
| 화면에서 입력하는 `actor_id` | 로그인 Session 또는 검증된 Token |
| 단일 Process Audit 목록 | 영구 Audit Table과 접근 제어 |
| 독립 Single Agent | 필요할 때만 Coordinator와 Handoff 추가 |

## 핵심 정리

```text
06 Agent Workflow
= Agent별 Goal과 Tool 권한
+ 공통 Python Agent Loop
+ MCP Tool Result 기반 LLM 재판단
+ 명시적인 종료 조건

07 Human Approval
= 06의 Agent Loop
+ Tool 위험도
+ 변경 직전 중단
+ 승인 Snapshot
+ 승인 후 재개
+ 중복 실행 방지와 Audit
```

이 설계에서 Agent는 단순히 LLM을 호출하는 함수가 아닙니다. Goal과 제한된 Tool을 가진 LLM이 State와 Tool Result를 관찰하면서 다음 행동을 반복 선택하고, Python Runtime이 실행과 종료를 통제하는 전체 구조가 AI Agent입니다.
