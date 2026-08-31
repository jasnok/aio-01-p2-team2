# Backend API Contract

## `POST /api/legal/questions`

```json
{
  "session_id": "demo-session",
  "category": "labor",
  "message": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

허용 카테고리는 `housing`, `labor`, `consumer`이다. 응답의 `laws`, `cases`, `sources`, `trace`는 항상 배열로 반환한다.

## 오류 코드 예정

- `INVALID_REQUEST`
- `UNSUPPORTED_CATEGORY`
- `MCP_UNAVAILABLE`
- `TOOL_VALIDATION_ERROR`
- `NO_RELEVANT_EVIDENCE`
- `LLM_TIMEOUT`
- `INTERNAL_ERROR`

