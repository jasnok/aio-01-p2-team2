# Architecture

```text
Streamlit Frontend :8501
  → FastAPI Backend :8000
  → Legal MCP Server :8001
  → PostgreSQL + pgvector :5432
```

- Frontend는 Backend만 호출한다.
- Backend는 Agent 실행, 제한, 최종 답변을 담당한다.
- MCP Server는 법률 검색 Tool과 표준 결과를 제공한다.
- Repository만 법률 DB에 접근한다.
- 현재 MCP endpoint는 LAN 연결 검증용 Mock이며 실제 MCP transport로 교체할 예정이다.

