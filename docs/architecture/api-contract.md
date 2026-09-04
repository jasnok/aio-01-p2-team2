# Frontend–Backend API 계약

기준 Endpoint는 `POST /api/legal/questions`입니다.

## 요청

```json
{
  "session_id": "web-uuid",
  "category": "labor",
  "question": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

- `category`: `housing`, `labor`, `consumer`
- `question`: 공백 제거 후 5~2,000자

## 응답 핵심 필드

```text
request_id, agent_id, status, termination_reason
question_summary, key_issues, answer
related_laws, similar_cases, sources
follow_up_questions, cautions, is_mock
```

실행 가능한 예시는 `tests/contract/fixtures/legal_question_response.json`에 있습니다. 응답 필드를 변경할 때 Backend Schema, Frontend View Model, Fixture와 계약 테스트를 한 PR에서 갱신합니다.
