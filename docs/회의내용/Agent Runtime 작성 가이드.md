# Agent Runtime 작성 가이드

이 문서는 `labor`부터 실제 Agent 흐름을 직접 작성하기 위한 연습 가이드다. 완성 코드를 복사하지 않고, 파일별 책임과 구현 순서를 이해하는 것이 목표다.

## 1. 먼저 기억할 구조

실행되는 Agent는 하나다. `labor`, `housing`, `consumer`는 각각 별도 실행기가 아니라 **Profile**이다.

```text
POST /api/legal/questions
→ registry에서 category Profile 선택
→ LegalAgentRuntime 하나 실행
→ Profile 규칙에 맞는 MCP Tool 선택
→ Evidence 검증
→ 근거 기반 응답
```

따라서 `labor_agent.py`에는 FastAPI Endpoint, DB 연결, HTTP 요청을 넣지 않는다.

| 파일 | 책임 |
|---|---|
| `agents/profiles.py` | 분야별 이름·설명·허용 Tool·안전 규칙 |
| `agents/registry.py` | category로 Profile 선택 |
| `agents/runtime.py` | 모든 Profile이 공유하는 실행 순서 |
| `mcp_clients/legal_mcp.py` | Legal MCP Tool 호출 |
| `services/legal_question_service.py` | Runtime 결과를 API 응답으로 변환 |
| `routers/legal.py` | HTTP 입력·Header·상태 코드 |

## 2. 첫 번째 완료 목표

처음에는 아래 한 사례만 끝까지 성공시키면 된다.

```text
"퇴직했는데 퇴직금을 받지 못했습니다."
→ labor Profile
→ search_cases
→ 판례 Evidence 최대 3개
→ 출처 URL 포함 응답
```

LLM 답변, 법령 검색, Housing/Consumer는 이 흐름이 통과한 뒤 추가한다.

## 3. `profiles.py` 작성 힌트

Labor Profile에는 바뀌지 않는 정책만 둔다.

```text
agent_id: labor
담당: 임금 체불, 퇴직금, 해고, 근로계약, 근로시간
허용 Tool: search_cases, search_laws, get_law_article
안전 규칙: 검색된 Evidence만 사용한다.
```

**힌트:** `AgentProfile`은 `frozen dataclass`라서 실행 중에 내용을 바꾸지 않는다. 질문별 상태는 `AgentState`에 저장한다.

## 4. `runtime.py` 작성 순서

공통 Runtime의 `run(profile, state)`는 다음 순서로 만든다.

1. Profile이 지원하는 분야인지 확인한다.
2. 현재 단계와 Trace를 기록한다.
3. 사용할 Tool이 `profile.allowed_tools`에 있는지 확인한다.
4. MCP Client를 호출한다.
5. MCP 응답의 `success`, `data` 형식을 확인한다.
6. Evidence 개수와 Trace를 저장한다.
7. 결과가 있으면 `COMPLETED`, 없으면 `no_results` 종료 사유를 만든다.

### Trace 기록 힌트

Trace에는 비밀번호, Token, DB URL, 전체 내부 예외를 넣지 않는다.

```python
# 예시 형태만 참고한다.
state.trace.append({
    "stage": "tool_selected",
    "tool": "search_cases",
    "category": profile.agent_id,
})
```

Tool이 끝난 뒤에는 결과 내용 전체가 아니라 개수만 남긴다.

```python
# 예시 형태만 참고한다.
state.trace.append({
    "stage": "tool_completed",
    "tool": "search_cases",
    "result_count": len(evidence),
})
```

### 종료 상태 힌트

| 상황 | `status` | `termination_reason` |
|---|---|---|
| Evidence 있음 | `completed` | `model_finished` |
| 검색 성공, 결과 없음 | `completed` | `no_results` |
| MCP 연결 실패 | `failed` | `mcp_unavailable` |
| 제한 시간 초과 | `failed` | `timeout` |
| 사용자가 취소 | `stopped` | `cancelled` |

## 5. Tool 선택 규칙을 늘리는 방법

처음에는 labor에서 항상 `search_cases`만 호출해도 된다. 이후 아래처럼 질문의 목적에 따라 분기한다.

```text
상황·사례 질문
예: "퇴직금을 못 받았어요"
→ search_cases

정확한 조문 질문
예: "근로기준법 제36조 내용이 뭐예요?"
→ get_law_article 또는 search_laws

복합 질문
예: "퇴직금 지급 기한과 비슷한 판례가 궁금해요"
→ search_cases → search_laws
```

**힌트:** Tool 이름을 `if`문에 바로 쓰기 전에 `ensure_tool_allowed(profile, tool_name)`을 호출한다. 이렇게 하면 다른 분야 Profile에 허용되지 않은 Tool을 실수로 쓰는 일을 막을 수 있다.

## 6. MCP 결과를 Evidence로 바꾸는 방법

MCP 결과는 아래를 기대한다.

```text
success: true 또는 false
data: Evidence 목록
```

각 Evidence에서 최소한 아래를 확인한다.

```text
title 존재
content 존재
source 존재
source.url 존재
category가 현재 Profile과 맞음
```

조건에 맞지 않는 자료는 답변에 넣지 않는다. 자료가 하나도 남지 않으면 “근거 부족” 또는 “검색 결과 없음”으로 처리한다.

## 7. `legal_question_service.py` 작성 힌트

Service는 Tool을 직접 고르지 않는다. 다음처럼 역할을 나눈다.

```text
Request 받기
→ registry에서 Profile 찾기
→ AgentState 만들기
→ Runtime 실행
→ Evidence를 API Schema로 검증
→ LegalQuestionResponse 만들기
```

응답에는 다음을 지킨다.

- 실제 MCP 결과면 `is_mock=false`
- Mock 응답이면 `is_mock=true`
- 결과가 없으면 빈 배열을 반환한다.
- 법률 자문, 승소 보장, 근거 없는 조문을 만들지 않는다.

## 8. 테스트를 먼저 작성하는 순서

1. `search_cases`가 호출됐는지 Mock 함수로 확인한다.
2. 결과 3개가 들어오면 `similar_cases`가 3개 이하인지 확인한다.
3. 빈 배열이면 HTTP 200과 `no_results`인지 확인한다.
4. MCP 실패면 502 `MCP_UNAVAILABLE`인지 확인한다.
5. MCP timeout이면 504 `UPSTREAM_TIMEOUT`인지 확인한다.
6. category가 labor가 아니면 Labor 전용 Runtime이 실행되지 않는지 확인한다.
7. Trace에 Token·비밀번호가 없는지 확인한다.

실행 명령:

```powershell
cd C:\aio-01-p2-team2
python -m pytest backend/tests -v
python -m pytest tests/contract -v
```

## 9. 직접 구현할 때의 작은 체크리스트

- [ ] `labor_agent.py`에 새로운 독립 Agent Loop를 만들지 않았다.
- [ ] Profile 선택은 `registry.py`를 거친다.
- [ ] 실제 MCP 호출은 `mcp_clients/legal_mcp.py`에서만 한다.
- [ ] Runtime은 최대 Tool 호출 수를 지킨다.
- [ ] MCP 실패를 Mock 성공 응답으로 바꾸지 않는다.
- [ ] Evidence 없는 답변을 만들지 않는다.
- [ ] `is_mock` 값이 실제 상태와 맞는다.
- [ ] 테스트가 통과한다.

## 10. 다음 확장 순서

```text
Labor search_cases
→ Evidence 검증
→ search_laws / get_law_article
→ Housing Profile 정책
→ Consumer Profile 정책
→ LLM 근거 요약
→ Agent Run polling과 실제 실행 연결
→ SSE
```
