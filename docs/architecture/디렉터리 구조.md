# 디렉터리 구조와 담당 영역

## 요청 처리 흐름

```text
Streamlit → FastAPI → AgentRuntime → Legal MCP → PostgreSQL + pgvector
```

데이터 수집은 요청 처리와 분리합니다.

```text
국가법령정보 Open API → 수집 → 정규화 → Upsert → Chunk → Embedding
```

## 담당 영역

| 파트 | 기본 작업 경로 | 외부와 연결되는 경계 |
|---|---|---|
| Frontend | `frontend/` | Backend HTTP API |
| Backend·Agent | `backend/` | Frontend API, MCP Client |
| Legal MCP | `legal_mcp/` | MCP Tool, DB Repository |
| Database·RAG | `database/` | Migration, 적재 모델 |

`tests/contract/fixtures`는 파트 사이의 공용 계약입니다. Fixture를 바꾸는 PR은 소비자와 제공자 양쪽 테스트를 함께 수정합니다.

## 의존 방향

- Frontend는 Backend만 호출합니다.
- Backend와 Agent는 DB를 직접 조회하지 않습니다.
- Legal MCP만 검색 Repository를 통해 법률 DB를 읽습니다.
- 수집 파이프라인은 사용자 요청과 분리해 실행합니다.
- Trace와 내부 실행 정보는 일반 사용자 화면에 노출하지 않습니다.

## 레거시 코드

`mcp_server/FOOD.py`와 Integration Smoke Test는 초기 네트워크 연결 확인용입니다. 정식 법률 기능은 `legal_mcp/`에 구현하며 레거시 코드를 새 기능에서 import하지 않습니다.
