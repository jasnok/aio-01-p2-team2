# Swagger → Backend → Legal MCP 테스트 체크리스트

목표는 Swagger에서 입력한 근로·퇴직금 질문이 실제 Legal MCP의 `search_cases`를 거쳐 판례 Evidence로 돌아오는지 확인하는 것이다.

```text
Swagger → Backend(192.100.200.195:8000) → Legal MCP(192.100.200.72:8011/mcp)
→ PostgreSQL + pgvector → search_cases → 판례 Evidence
```

## 자동 확인 완료

- [x] Backend의 Legal MCP 주소 기본값이 `http://192.100.200.72:8011/mcp`이다.
- [x] Food MCP는 공통 MCP Client 등록 대상에서 제외했다.
- [x] `labor` Profile은 공통 `LegalAgentRuntime`에서 `search_cases`를 호출한다.
- [x] MCP 검색 결과가 없으면 `200`, `is_mock=false`, Evidence 빈 배열과 `no_results` 종료 상태를 반환한다.
- [x] Mock 모드와 실제 MCP 모드를 분리했다. 실제 모드에서 MCP 연결 실패는 Mock 답변으로 바꾸지 않고 `502` 또는 `504`로 반환한다.

## MCP 담당자가 확인할 것

- [ ] MCP 서버가 `192.100.200.72:8011`에서 실행 중이다.
- [ ] MCP endpoint는 FastMCP Streamable HTTP 주소인 `/mcp`를 제공한다.
- [ ] Tool 목록에 `search_cases`가 있다.
- [ ] PostgreSQL·pgvector가 연결되어 있고, `legal_documents`, `legal_chunks`에 labor 판례 데이터가 있다.
- [ ] Ollama 임베딩 서버와 DB 벡터 차원이 일치한다.

## Backend 담당자가 실행할 것

1. `backend/.env`에 아래를 설정한다. 실제 비밀값은 커밋하지 않는다.

   ```env
   BACKEND_MOCK_MODE=false
   LEGAL_MCP_URL=http://192.100.200.72:8011/mcp
   MCP_REQUEST_TIMEOUT_SECONDS=10
   ```

2. Backend를 실행한다.

   ```powershell
   cd C:\aio-01-p2-team2
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. `http://192.100.200.195:8000/docs`에서 `GET /health`를 실행한다.

   - [ ] `dependencies.mcp`가 `ok`다.
   - [ ] `is_mock`가 `false`다.

4. `POST /api/legal/questions`을 실행한다.

   Header:

   ```text
   Idempotency-Key: swagger-labor-mcp-001
   ```

   Body:

   ```json
   {
     "session_id": "swagger-labor-mcp-001",
     "category": "labor",
     "question": "퇴직했는데 퇴직금을 받지 못했습니다."
   }
   ```

5. 성공 기준을 확인한다.

   - [ ] HTTP `200`
   - [ ] `is_mock: false`
   - [ ] `agent_id: labor`
   - [ ] `termination_reason: model_finished` 또는 결과 없음이면 `no_results`
   - [ ] 결과가 있으면 `similar_cases`에 최대 3개
   - [ ] 각 결과에 `source.url`이 있다.

## 실패 시 쉬운 판단

| 결과 | 뜻 | 먼저 확인할 곳 |
|---|---|---|
| `502 MCP_UNAVAILABLE` | Backend가 MCP에 연결하거나 Tool 호출을 못 함 | MCP 실행 여부, IP·포트, `/mcp`, Tool 이름 |
| `504 UPSTREAM_TIMEOUT` | MCP·DB·임베딩이 10초 안에 끝나지 않음 | Ollama, DB, 네트워크 |
| `200` + `no_results` | 연결은 성공했지만 검색 데이터가 없음 | labor 판례 Seed, category, 임베딩 차원 |
| `is_mock: true` | Backend가 아직 Mock 모드 | `BACKEND_MOCK_MODE=false` 확인 |
