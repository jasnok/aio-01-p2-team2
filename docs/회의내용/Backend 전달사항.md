# Backend 연동 확인 결과 및 남은 사항

Frontend 개선 과정에서 실제 연동 전에 Backend가 확인해야 할 항목만 모았습니다.

## 반영·검증 완료

- [x] 읽은 알림 삭제를 `DELETE /api/notifications/read-items`로 제공한다.
- [x] 관리자는 `reason`만으로 모든 사용자 질문을 삭제할 수 있다.
- [x] 질문 목록은 답변 대기 우선, 같은 상태에서는 최신순으로 정렬한다.
- [x] 공개 FAQ는 고정 항목 우선으로 정렬한다.
- [x] 댓글 삭제는 `content` 없이 `comment_password`만 받는다.
- [x] Agent Run API 네 경로가 OpenAPI에 존재한다.
- [x] MCP 주소를 `192.100.200.72:8013/mcp`로 변경했다.

## 추가 확인 필요

- [ ] 관리자 삭제 감사 로그가 실제 저장되는지 확인한다.
- [ ] Session 만료 시 `401 AUTH_SESSION_EXPIRED`를 일관되게 반환하는지 확인한다.
- [ ] 동일 `Idempotency-Key` 중복 실행 방지를 확인한다.
- [ ] 실제 MCP 법률 Tool 실행 결과를 확인한다.
- [ ] Redis를 연결하고 Session·진행 상태 TTL을 확인한다.

## Agent 진행 상태 API 제안

먼저 polling으로 연결하고 안정화 후 SSE를 추가합니다.

```http
POST /api/agent-runs
GET  /api/agent-runs/{run_id}
POST /api/agent-runs/{run_id}/cancel
GET  /api/agent-runs/{run_id}/events
```

상태는 `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`를 사용합니다.

- `POST`에는 `Idempotency-Key`를 필수로 받는다.
- 중복 Key 요청은 같은 `run_id`와 현재 상태를 반환한다.
- 진행 단계와 최근 상태는 Redis에 TTL과 함께 저장한다.
- 완료 결과와 필요한 영구 이력만 PostgreSQL에 저장한다.
- SSE가 끊기면 Frontend가 `GET /api/agent-runs/{run_id}` polling으로 복구할 수 있어야 한다.

## MCP 주소 변경

학원 네트워크 MCP 주소가 다음과 같이 변경되었습니다.

```text
http://192.100.200.72:8013
Streamable HTTP endpoint: http://192.100.200.72:8013/mcp
```

MCP 서버에는 현재 `/health`가 없고 `/mcp` 요청에는 서버가 응답합니다. Backend의 `/api/integration/mcp`에서 실제 MCP 초기화·Tool 목록 확인 결과를 반환해 주세요.

## Backend 완료 후 함께 확인할 것

- [x] OpenAPI 문서와 `docs/architecture/API 명세서.md` 비교
- [x] 회원·비회원·관리자 질문 삭제 권한 테스트
- [x] 고정 FAQ 정렬과 질문 게시판 정렬 테스트
- [x] 알림 모두 읽음·읽은 알림 일괄 삭제 테스트
- [ ] 동일 `Idempotency-Key`를 두 번 보내도 실행이 한 번만 생성되는지 테스트
- [ ] Backend → MCP `8013` 연결과 Tool 호출 테스트
- [x] Backend → DB·Redis 상태가 `/health`에 실제/Mock으로 구분되는지 확인 (`database=ok`, `redis=disabled`)
