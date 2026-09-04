# 첫 통합 순서

첫 목표는 퇴직금 질문 한 건을 끝까지 연결하는 것입니다.

```text
Frontend 질문
→ POST /api/legal/questions
→ LaborAgent
→ search_cases
→ Legal MCP
→ PostgreSQL + pgvector
→ 공식 판례 Top 3
→ Frontend 카드
```

## 권장 병렬 브랜치

- `feature/frontend-legal-dashboard`
- `feature/backend-agent-runtime`
- `feature/mcp-legal-search-tools`
- `feature/db-legal-ingestion`

각 파트는 `tests/contract/fixtures`를 기준으로 독립 구현하고, 계약 변경이 필요하면 관련 담당자에게 먼저 공유합니다.
